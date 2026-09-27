from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class Role(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    CLASS_REPRESENTATIVE = "CLASS_REPRESENTATIVE", "Class representative"
    TEACHER = "TEACHER", "Teacher"
    ADMIN = "ADMIN", "Administrator"


class BloodGroup(models.TextChoices):
    A_POSITIVE = "A+", "A+"
    A_NEGATIVE = "A-", "A-"
    B_POSITIVE = "B+", "B+"
    B_NEGATIVE = "B-", "B-"
    AB_POSITIVE = "AB+", "AB+"
    AB_NEGATIVE = "AB-", "AB-"
    O_POSITIVE = "O+", "O+"
    O_NEGATIVE = "O-", "O-"


class UserManager(BaseUserManager):
    """Manager that keeps e-mail as the canonical login identifier."""

    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An e-mail address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", Role.STUDENT)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff and is_superuser set to True.")
        return self._create(email, password, **extra)


class User(AbstractUser):
    """
    A TEL platform account.

    The account carries the identity used for authorisation. Academic placement
    (campus / class / section) lives on ``StudentProfile`` because it is
    maintained by TEL core, not by the student.
    """

    username = None
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=160)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.STUDENT, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    phone = models.CharField(max_length=24, blank=True)

    # Identifier issued by the TEL core system, used by the integration adapter.
    tel_user_ref = models.CharField(max_length=64, blank=True, db_index=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        ordering = ("full_name",)

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.full_name} <{self.email}>"

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        parts = self.full_name.strip().split()
        return parts[0] if parts else self.full_name

    def mark_password_changed(self) -> None:
        self.password_changed_at = timezone.now()
        self.save(update_fields=["password_changed_at"])


class StudentProfile(TimeStampedModel):
    """Academic placement of a student. Maintained by TEL core, read-only for students."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_LEAVE = "ON_LEAVE", "On leave"
        GRADUATED = "GRADUATED", "Graduated"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_code = models.CharField(max_length=32, unique=True, db_index=True)
    roll_number = models.CharField(max_length=32, blank=True)
    campus = models.ForeignKey(
        "academics.Campus", on_delete=models.PROTECT, related_name="students", null=True
    )
    program = models.ForeignKey(
        "academics.Program", on_delete=models.PROTECT, related_name="students", null=True
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.PROTECT, related_name="students", null=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.PROTECT, related_name="students", null=True
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.PROTECT, related_name="students", null=True
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=16, blank=True)
    blood_group = models.CharField(max_length=8, choices=BloodGroup.choices, blank=True)
    photo = models.ImageField(upload_to="students/%Y/%m/", null=True, blank=True)

    guardian_name = models.CharField(max_length=160, blank=True)
    guardian_relation = models.CharField(max_length=40, blank=True)
    guardian_phone = models.CharField(max_length=24, blank=True)
    home_address = models.TextField(blank=True)

    admission_date = models.DateField(null=True, blank=True)
    last_synced_from_tel = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("student_code",)
        indexes = [models.Index(fields=["campus", "program", "class_room", "section"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.student_code} — {self.user.full_name}"

    @property
    def is_placeable(self) -> bool:
        """True when the profile is complete enough to serve academic data."""
        return bool(self.class_room_id and self.section_id and self.campus_id and self.academic_year_id)

    def class_label(self) -> str:
        if not self.class_room:
            return "Class not assigned"
        if self.section:
            return f"{self.class_room} — {self.section}"
        return str(self.class_room)


class TeacherProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    employee_code = models.CharField(max_length=32, unique=True)
    designation = models.CharField(max_length=80, blank=True)
    campus = models.ForeignKey(
        "academics.Campus", on_delete=models.PROTECT, related_name="teachers", null=True
    )
    subjects = models.ManyToManyField("academics.Subject", related_name="teachers", blank=True)

    class Meta:
        ordering = ("employee_code",)

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.employee_code} — {self.user.full_name}"
