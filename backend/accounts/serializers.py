from __future__ import annotations

from django.contrib.auth import authenticate, password_validation
from django.db import transaction
from rest_framework import serializers

from accounts.models import Role, StudentProfile, User
from accounts.permissions import capabilities_for
from academics.selectors import campus_brief, class_brief, program_brief


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class CampusBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class ProgramBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    level = serializers.CharField(read_only=True)


class ClassBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)


class SectionBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class AcademicYearBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)


class StudentProfileSerializer(serializers.ModelSerializer):
    campus = CampusBriefSerializer(read_only=True)
    program = ProgramBriefSerializer(read_only=True)
    class_room = ClassBriefSerializer(read_only=True)
    section = SectionBriefSerializer(read_only=True)
    academic_year = AcademicYearBriefSerializer(read_only=True)
    class_display = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "student_code",
            "roll_number",
            "campus",
            "program",
            "class_room",
            "section",
            "academic_year",
            "class_display",
            "status",
            "date_of_birth",
            "gender",
            "blood_group",
            "guardian_name",
            "guardian_relation",
            "guardian_phone",
            "home_address",
            "admission_date",
            "photo_url",
            "last_synced_from_tel",
        ]
        read_only_fields = fields

    def get_class_display(self, obj: StudentProfile) -> str:
        return obj.class_label()

    def get_photo_url(self, obj: StudentProfile) -> str | None:
        if not obj.photo:
            return None
        request = self.context.get("request")
        url = obj.photo.url
        return request.build_absolute_uri(url) if request else url


class UserSerializer(serializers.ModelSerializer):
    student_profile = StudentProfileSerializer(read_only=True)
    capabilities = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "phone",
            "initials",
            "capabilities",
            "student_profile",
        ]
        read_only_fields = fields

    def get_capabilities(self, obj: User) -> list[str]:
        return capabilities_for(obj.role)

    def get_initials(self, obj: User) -> str:
        parts = [p for p in obj.full_name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "ST"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Only contact details are student editable.

    Academic placement (campus, program, class, section, year, student code,
    roll number) and identity fields are owned by TEL core and are intentionally
    absent from this serializer.
    """

    class Meta:
        model = User
        fields = ["full_name", "phone"]

    def validate_full_name(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise serializers.ValidationError("Please enter your full name.")
        if len(cleaned) > 160:
            raise serializers.ValidationError("Name is too long.")
        return cleaned


class StudentContactUpdateSerializer(serializers.ModelSerializer):
    """Personal contact details a student may correct themselves."""

    class Meta:
        model = StudentProfile
        fields = [
            "guardian_name",
            "guardian_relation",
            "guardian_phone",
            "home_address",
            "blood_group",
        ]

    def validate_guardian_phone(self, value: str) -> str:
        digits = "".join(ch for ch in (value or "") if ch.isdigit())
        if value and not (10 <= len(digits) <= 15):
            raise serializers.ValidationError("Enter a valid phone number.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value, self.context["request"].user)
        return value

    @transaction.atomic
    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.mark_password_changed()
        user.save(update_fields=["password", "password_changed_at", "updated_at"] if hasattr(user, "updated_at") else ["password", "password_changed_at"])
        return user


class PasswordForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


class RoleSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


def authenticate_user(email: str, password: str) -> User | None:
    user = authenticate(
        request=None, username=email.lower().strip(), password=password
    )
    if user is not None and not user.is_active:
        return None
    return user


__all__ = [
    "AcademicYearBriefSerializer",
    "CampusBriefSerializer",
    "ClassBriefSerializer",
    "LoginSerializer",
    "PasswordChangeSerializer",
    "PasswordForgotSerializer",
    "PasswordResetSerializer",
    "ProgramBriefSerializer",
    "ProfileUpdateSerializer",
    "RoleSerializer",
    "SectionBriefSerializer",
    "StudentContactUpdateSerializer",
    "StudentProfileSerializer",
    "UserSerializer",
    "authenticate_user",
    "campus_brief",
    "class_brief",
    "program_brief",
]
