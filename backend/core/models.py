from __future__ import annotations

from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class NotificationState(models.TextChoices):
    UNREAD = "UNREAD", "Unread"
    READ = "READ", "Read"
    ARCHIVED = "ARCHIVED", "Archived"


class NotificationCategory(models.TextChoices):
    RESULT = "RESULT", "Results"
    PAPER = "PAPER", "Papers"
    TIMETABLE = "TIMETABLE", "Timetable"
    ASSIGNMENT = "ASSIGNMENT", "Assignments"
    ANNOUNCEMENT = "ANNOUNCEMENT", "Announcements"
    ATTENDANCE = "ATTENDANCE", "Attendance"
    REQUEST = "REQUEST", "Requests"
    CALENDAR = "CALENDAR", "Calendar"
    SYSTEM = "SYSTEM", "System"


class NotificationQuerySet(models.QuerySet):
    def visible_to(self, user) -> "NotificationQuerySet":
        return self.filter(recipient=user, is_archived=False)

    def unread(self) -> "NotificationQuerySet":
        return self.filter(state=NotificationState.UNREAD)


class Notification(models.Model):
    """
    A real notification record.

    Notifications are written by the backend when a workflow completes (a result
    is published, a timetable goes live, a request is answered) — they are never
    fabricated in the client.
    """

    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(
        max_length=20, choices=NotificationCategory.choices, default=NotificationCategory.SYSTEM, db_index=True
    )
    state = models.CharField(
        max_length=12, choices=NotificationState.choices, default=NotificationState.UNREAD, db_index=True
    )
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    action_url = models.CharField(max_length=300, blank=True)
    action_label = models.CharField(max_length=60, blank=True)

    # Deduplication: the same event must not notify the same student twice.
    dedupe_key = models.CharField(max_length=200, blank=True, db_index=True)

    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient", "is_archived", "state"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=models.Q(dedupe_key__gt=""),
                name="uniq_notification_per_recipient_key",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.category} → {self.recipient_id}: {self.title}"

    def mark_read(self) -> None:
        if self.state == NotificationState.UNREAD:
            self.state = NotificationState.READ
            self.read_at = timezone.now()
            self.save(update_fields=["state", "read_at"])


class AuditLog(models.Model):
    """
    Append-only trail of sensitive actions.

    Records are never updated or deleted through the application, so an
    administrator cannot quietly rewrite history.
    """

    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="audit_entries", null=True
    )
    actor_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=64, blank=True, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True)
    summary = models.CharField(max_length=240, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["entity_type", "entity_id"])]
        verbose_name = "audit log entry"

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} by {self.actor_id or 'system'}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit log entries are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - defensive
        raise ValueError("Audit log entries cannot be deleted.")


class UploadRecord(models.Model):
    """Tracks every accepted upload so storage can be audited and pruned."""

    class Purpose(models.TextChoices):
        PAPER = "PAPER", "Paper"
        TIMETABLE_IMAGE = "TIMETABLE_IMAGE", "Timetable image"
        TIMETABLE_PDF = "TIMETABLE_PDF", "Timetable PDF"
        RESOURCE = "RESOURCE", "Resource"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        SUBMISSION = "SUBMISSION", "Assignment submission"
        REQUEST = "REQUEST", "Request attachment"
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement attachment"
        PROFILE_PHOTO = "PROFILE_PHOTO", "Profile photo"

    class Visibility(models.TextChoices):
        OWNER = "OWNER", "Owner only"
        CLASS = "CLASS", "Class members"
        PUBLISHED = "PUBLISHED", "Published record"
        STAFF = "STAFF", "TEL staff"

    uploader = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="uploads", null=True
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices, db_index=True)
    storage_path = models.CharField(max_length=300)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64, db_index=True)

    #: Who may stream this file back. Enforced by ``core.views.FileAccessView``.
    visibility = models.CharField(
        max_length=16, choices=Visibility.choices, default=Visibility.OWNER, db_index=True
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.SET_NULL, related_name="file_grants", null=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.SET_NULL, related_name="file_grants", null=True
    )
    allowed_user_ids = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["checksum", "is_active"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.purpose}: {self.original_name}"

