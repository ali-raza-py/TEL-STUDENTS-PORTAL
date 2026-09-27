from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel, UUIDPublicIdModel


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"

    @classmethod
    def label_for(cls, value: int) -> str:
        return cls(value).label


class Campus(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=24, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "campuses"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.name


class Program(TimeStampedModel):
    class Level(models.TextChoices):
        XI = "XI", "Intermediate (XI–XII)"
        UNDERGRADUATE = "UG", "Undergraduate"

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    level = models.CharField(max_length=8, choices=Level.choices, default=Level.XI)
    department = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("level", "name")

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.name


class AcademicYear(TimeStampedModel):
    code = models.CharField(max_length=24, unique=True)
    label = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ("-start_date",)

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.label

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)


class ClassRoom(TimeStampedModel):
    """
    A class group, e.g. *XI Computer Science — Jinnah Campus*.

    A ``ClassRoom`` is a programme run at a campus for an academic year; the
    ``Section`` (A/B) sits underneath it.
    """

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="class_rooms")
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name="class_rooms")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="class_rooms"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("program__name", "name")
        indexes = [models.Index(fields=["campus", "program"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.name} · {self.program.name} · {self.campus.name}"


class Section(TimeStampedModel):
    class_room = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=16)
    capacity = models.PositiveSmallIntegerField(default=50)
    room = models.CharField(max_length=48, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["class_room", "name"], name="uniq_section_per_class"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.class_room.code} — {self.name}"

    @property
    def display_name(self) -> str:
        return f"{self.class_room.name} — {self.name}"


class Subject(TimeStampedModel):
    #: Accent tokens the frontend maps to its design system palette. A subject's
    #: token is derived from its code so a subject always looks the same without
    #: any colour being hardcoded in a component.
    COLOR_TOKENS = ("sage", "mint", "sky", "sand", "clay", "lilac")

    class Kind(models.TextChoices):
        THEORY = "THEORY", "Theory"
        PRACTICAL = "PRACTICAL", "Practical"
        BOTH = "BOTH", "Theory & practical"

    code = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=140)
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="subjects")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.THEORY)
    credit_hours = models.DecimalField(max_digits=4, decimal_places=1, default=3.0)
    is_elective = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.code} — {self.name}"

    @property
    def color_token(self) -> str:
        digest = sum(ord(ch) for ch in self.code.upper())
        return self.COLOR_TOKENS[digest % len(self.COLOR_TOKENS)]


class SubjectOffering(TimeStampedModel):
    """A subject taught to a specific class/section in a specific year."""

    class_room = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="offerings")
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="offerings", null=True, blank=True
    )
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="offerings")
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="teachings", null=True
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="offerings"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("subject__code",)
        constraints = [
            models.UniqueConstraint(
                fields=["class_room", "section", "subject", "academic_year"],
                name="uniq_offering_per_class_subject",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.subject.code} @ {self.class_room.code}"


class ClassRepresentative(TimeStampedModel):
    """
    Delegation record: one student per class section may manage the timetable
    for that section. The role grants timetable submission only — never access
    to marks, attendance, other students or administration.
    """

    class_room = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="representatives")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="representatives")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="representative_roles"
    )
    assigned_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="representative_assignments", null=True
    )
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-is_active", "class_room__code")
        constraints = [
            models.UniqueConstraint(
                fields=["class_room", "section", "is_active"],
                condition=models.Q(is_active=True),
                name="uniq_active_rep_per_section",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.user.full_name} — {self.section}"


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


class TimetableStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Pending review"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    APPROVED = "APPROVED", "Approved"
    PUBLISHED = "PUBLISHED", "Published"
    REJECTED = "REJECTED", "Rejected"
    CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
    ARCHIVED = "ARCHIVED", "Archived"


#: Only these states are ever visible to students.
STUDENT_VISIBLE_TIMETABLE_STATES = {TimetableStatus.PUBLISHED}


class Timetable(TimeStampedModel, UUIDPublicIdModel):
    """
    A versioned weekly timetable for one class section.

    Publishing archives the previous published version so a class always has
    exactly one authoritative timetable, while history remains retrievable.
    """

    class_room = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="timetables")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetables")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="timetables"
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=TimetableStatus.choices, default=TimetableStatus.DRAFT, db_index=True
    )
    title = models.CharField(max_length=160, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=32, default="PORTAL")
    change_note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="timetables_created", null=True
    )
    approved_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="timetables_approved", null=True
    )
    published_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-version", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["class_room", "section", "academic_year", "version"],
                name="uniq_timetable_version",
            )
        ]
        indexes = [models.Index(fields=["class_room", "section", "status"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.section} timetable v{self.version} ({self.status})"

    @property
    def is_visible_to_students(self) -> bool:
        return self.status == TimetableStatus.PUBLISHED

    def next_version_number(self) -> int:
        latest = (
            Timetable.objects.filter(
                class_room=self.class_room, section=self.section, academic_year=self.academic_year
            )
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        return (latest or 0) + 1


class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name="entries")
    day_of_week = models.PositiveSmallIntegerField(choices=Weekday.choices, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="timetable_entries")
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="timetable_entries", null=True, blank=True
    )
    room = models.CharField(max_length=64, blank=True)
    campus = models.ForeignKey(
        Campus, on_delete=models.SET_NULL, related_name="timetable_entries", null=True, blank=True
    )
    section_override = models.ForeignKey(
        Section, on_delete=models.SET_NULL, related_name="timetable_entries", null=True, blank=True
    )
    note = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("day_of_week", "start_time")
        indexes = [models.Index(fields=["timetable", "day_of_week", "start_time"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.timetable} · {Weekday.label_for(self.day_of_week)} {self.start_time:%H:%M}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after the start time."})


class TimetableSubmission(TimeStampedModel, UUIDPublicIdModel):
    """
    A timetable proposed by the class representative (or TEL staff).

    A submission never becomes visible to students on its own: it must pass
    review and be published.
    """

    class_room = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="timetable_submissions")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetable_submissions")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="timetable_submissions"
    )
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="timetable_submissions", null=True
    )
    status = models.CharField(
        max_length=20, choices=TimetableStatus.choices, default=TimetableStatus.SUBMITTED, db_index=True
    )
    summary = models.CharField(max_length=240, blank=True)
    change_note = models.TextField(blank=True)

    # Structured payload: list of {day, start, end, subject_code, subject_name,
    # teacher, room}. Validated against the class's offered subjects.
    entries_payload = models.JSONField(default=list, blank=True)

    image_file = models.FileField(upload_to="timetable/images/%Y/%m/", null=True, blank=True)
    pdf_file = models.FileField(upload_to="timetable/pdfs/%Y/%m/", null=True, blank=True)

    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="timetable_reviews", null=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resulting_timetable = models.ForeignKey(
        Timetable, on_delete=models.SET_NULL, related_name="approved_from", null=True
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["class_room", "section", "status"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"Submission #{self.pk} — {self.section} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in {
            TimetableStatus.SUBMITTED,
            TimetableStatus.UNDER_REVIEW,
            TimetableStatus.CHANGES_REQUESTED,
        }
