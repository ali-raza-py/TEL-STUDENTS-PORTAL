from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel, UUIDPublicIdModel


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    EXCUSED = "EXCUSED", "Excused"
    ON_DUTY = "ON_DUTY", "On duty"


ATTENDED_STATUSES = {
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.ON_DUTY,
    AttendanceStatus.EXCUSED,
}


class AttendanceRecord(models.Model):
    """One student, one subject, one date. Mirrored from TEL core."""

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="attendance"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="attendance_records"
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.PROTECT, related_name="attendance_records"
    )
    date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=10, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT, db_index=True
    )
    period_label = models.CharField(max_length=32, blank=True)
    note = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="attendance_marked", null=True
    )
    source = models.CharField(max_length=12, default="TEL_CORE")
    external_ref = models.CharField(max_length=80, blank=True, db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date", "subject__code")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject", "date"], name="uniq_attendance_per_day"
            )
        ]
        indexes = [models.Index(fields=["student", "date"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.student_id} · {self.subject_id} · {self.date} · {self.status}"

    @property
    def counts_as_attended(self) -> bool:
        return self.status in ATTENDED_STATUSES


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


class AssignmentStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    SUBMITTED = "SUBMITTED", "Submitted"
    LATE = "LATE", "Late"
    REVIEWED = "REVIEWED", "Reviewed"


class Assignment(TimeStampedModel, UUIDPublicIdModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="assignments"
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.CASCADE, related_name="assignments"
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="assignments", null=True, blank=True
    )
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="assignments", null=True
    )
    assigned_on = models.DateField(default=timezone.localdate, db_index=True)
    due_on = models.DateField(db_index=True)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("10"))
    attachment = models.FileField(upload_to="assignments/%Y/%m/", null=True, blank=True)
    attachment_name = models.CharField(max_length=180, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-due_on",)
        indexes = [models.Index(fields=["class_room", "section", "due_on"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.title} ({self.subject.code})"


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="assignment_submissions"
    )
    status = models.CharField(
        max_length=14, choices=AssignmentStatus.choices, default=AssignmentStatus.SUBMITTED
    )
    file = models.FileField(upload_to="assignment-submissions/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="assignments_reviewed", null=True
    )
    feedback = models.TextField(blank=True)
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"], name="uniq_submission_per_assignment"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.assignment_id} · {self.student_id}"


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ResourceCategory(models.TextChoices):
    NOTES = "NOTES", "Notes"
    SYLLABUS = "SYLLABUS", "Syllabus"
    PREVIOUS_PAPERS = "PREVIOUS_PAPERS", "Previous papers"
    ANSWER_KEYS = "ANSWER_KEYS", "Answer keys"
    STUDY_MATERIAL = "STUDY_MATERIAL", "Study material"
    FORMS = "FORMS", "Forms"
    NOTICES = "NOTICES", "Notices"
    OTHER = "OTHER", "Other"


class Resource(TimeStampedModel, UUIDPublicIdModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=ResourceCategory.choices, default=ResourceCategory.OTHER, db_index=True
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.SET_NULL, related_name="resources", null=True, blank=True
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.CASCADE, related_name="resources", null=True, blank=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="resources", null=True, blank=True
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.SET_NULL, related_name="resources", null=True, blank=True
    )
    chapter = models.CharField(max_length=140, blank=True, db_index=True)
    file = models.FileField(upload_to="resources/%Y/%m/", null=True, blank=True)
    external_url = models.URLField(max_length=400, blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="resources", null=True
    )
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [models.Index(fields=["category", "subject"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.title


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


class AudienceType(models.TextChoices):
    ALL_STUDENTS = "ALL_STUDENTS", "All TEL students"
    CAMPUS = "CAMPUS", "Campus"
    PROGRAM = "PROGRAM", "Programme"
    CLASS = "CLASS", "Class"
    SECTION = "SECTION", "Section"
    ACADEMIC_YEAR = "ACADEMIC_YEAR", "Academic year"
    STAFF = "STAFF", "TEL staff only"


class Announcement(TimeStampedModel, UUIDPublicIdModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(
        max_length=16, choices=AudienceType.choices, default=AudienceType.ALL_STUDENTS, db_index=True
    )
    campus = models.ForeignKey(
        "academics.Campus", on_delete=models.CASCADE, related_name="announcements", null=True, blank=True
    )
    program = models.ForeignKey(
        "academics.Program", on_delete=models.CASCADE, related_name="announcements", null=True, blank=True
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.CASCADE, related_name="announcements", null=True, blank=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="announcements", null=True, blank=True
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE, related_name="announcements", null=True, blank=True
    )
    attachment = models.FileField(upload_to="announcements/%Y/%m/", null=True, blank=True)
    attachment_name = models.CharField(max_length=180, blank=True)
    is_pinned = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="announcements", null=True
    )

    class Meta:
        ordering = ("-is_pinned", "-published_at")
        indexes = [models.Index(fields=["audience", "published_at"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.title

    def targets(self, profile) -> bool:
        if profile is None:
            return False
        checks = {
            AudienceType.ALL_STUDENTS: True,
            AudienceType.CAMPUS: self.campus_id is None or self.campus_id == profile.campus_id,
            AudienceType.PROGRAM: self.program_id is None or self.program_id == profile.program_id,
            AudienceType.CLASS: self.class_room_id is None or self.class_room_id == profile.class_room_id,
            AudienceType.SECTION: self.section_id is None or self.section_id == profile.section_id,
            AudienceType.ACADEMIC_YEAR: (
                self.academic_year_id is None or self.academic_year_id == profile.academic_year_id
            ),
            AudienceType.STAFF: False,
        }
        return bool(checks.get(self.audience, False))


# ---------------------------------------------------------------------------
# Academic calendar
# ---------------------------------------------------------------------------


class AcademicEventType(models.TextChoices):
    TEST = "TEST", "Test"
    EXAM = "EXAM", "Exam"
    ASSIGNMENT_DUE = "ASSIGNMENT_DUE", "Assignment deadline"
    HOLIDAY = "HOLIDAY", "Holiday"
    TEL_EVENT = "TEL_EVENT", "TEL event"
    RESULT_PUBLICATION = "RESULT_PUBLICATION", "Result publication"


class AcademicEvent(TimeStampedModel, UUIDPublicIdModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(
        max_length=20, choices=AcademicEventType.choices, default=AcademicEventType.TEL_EVENT, db_index=True
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    campus = models.ForeignKey(
        "academics.Campus", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    program = models.ForeignKey(
        "academics.Program", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="events", null=True
    )

    class Meta:
        ordering = ("starts_at",)
        indexes = [models.Index(fields=["starts_at", "event_type"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.title} ({self.get_event_type_display()})"

    def targets(self, profile) -> bool:
        if profile is None:
            return False
        if self.campus_id and self.campus_id != profile.campus_id:
            return False
        if self.program_id and self.program_id != profile.program_id:
            return False
        if self.class_room_id and self.class_room_id != profile.class_room_id:
            return False
        if self.section_id and self.section_id != profile.section_id:
            return False
        return True


# ---------------------------------------------------------------------------
# Requests & feedback
# ---------------------------------------------------------------------------


class RequestType(models.TextChoices):
    ATTENDANCE_CORRECTION = "ATTENDANCE_CORRECTION", "Attendance correction"
    RESULT_CORRECTION = "RESULT_CORRECTION", "Result correction"
    PROFILE_CORRECTION = "PROFILE_CORRECTION", "Profile correction"
    TIMETABLE_ISSUE = "TIMETABLE_ISSUE", "Timetable issue"
    LEAVE = "LEAVE", "Leave request"
    DOCUMENT = "DOCUMENT", "Document request"
    TECHNICAL = "TECHNICAL", "Technical problem"
    OTHER = "OTHER", "Other"


class RequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_REVIEW = "IN_REVIEW", "In review"
    RESOLVED = "RESOLVED", "Resolved"
    REJECTED = "REJECTED", "Rejected"
    CLOSED = "CLOSED", "Closed"


OPEN_REQUEST_STATUSES = {RequestStatus.PENDING, RequestStatus.IN_REVIEW}


class StudentRequest(UUIDPublicIdModel):
    ticket_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="requests"
    )
    request_type = models.CharField(max_length=28, choices=RequestType.choices, db_index=True)
    subject_line = models.CharField(max_length=180)
    description = models.TextField()
    related_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to="requests/%Y/%m/", null=True, blank=True)
    attachment_name = models.CharField(max_length=180, blank=True)

    status = models.CharField(
        max_length=12, choices=RequestStatus.choices, default=RequestStatus.PENDING, db_index=True
    )
    admin_response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="requests_answered", null=True
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "status"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.ticket_id} · {self.subject_line}"

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = self._generate_ticket_id()
        return super().save(*args, **kwargs)

    @staticmethod
    def _generate_ticket_id() -> str:
        import random
        import string

        alphabet = string.ascii_uppercase + string.digits
        while True:
            candidate = "TEL-" + "".join(random.choice(alphabet) for _ in range(7))
            if not StudentRequest.objects.filter(ticket_id=candidate).exists():
                return candidate


class FeedbackCategory(models.TextChoices):
    PORTAL = "PORTAL", "Student portal"
    RESOURCES = "RESOURCES", "Academic resources"
    COMMUNICATION = "COMMUNICATION", "Communication"
    TIMETABLE = "TIMETABLE", "Timetable"
    OTHER = "OTHER", "Other"


class Feedback(UUIDPublicIdModel):
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="feedback", null=True
    )
    category = models.CharField(
        max_length=16, choices=FeedbackCategory.choices, default=FeedbackCategory.PORTAL
    )
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=12, default="NEW")
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.get_category_display()} — {self.pk}"
