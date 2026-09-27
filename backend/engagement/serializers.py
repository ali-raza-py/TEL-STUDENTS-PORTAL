from __future__ import annotations

from rest_framework import serializers

from engagement.models import (
    AcademicEvent,
    Announcement,
    Assignment,
    AssignmentSubmission,
    Feedback,
    RequestStatus,
    RequestType,
    Resource,
    ResourceCategory,
    StudentRequest,
)


def _file_url(value, context) -> str | None:
    if not value:
        return None
    from core.models import UploadRecord

    record = UploadRecord.objects.filter(storage_path=value.name, is_active=True).first()
    if record is None:
        return None
    request = context.get("request")
    path = f"/api/files/{record.pk}/"
    return request.build_absolute_uri(path) if request else path


class AttendanceRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    subject_id = serializers.IntegerField()
    subject_code = serializers.CharField(source="subject.code")
    subject_name = serializers.CharField(source="subject.name")
    subject_color = serializers.CharField(source="subject.color_token")
    status = serializers.CharField()
    status_label = serializers.CharField(source="get_status_display")
    period_label = serializers.CharField()
    note = serializers.CharField()


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "status",
            "file_url",
            "notes",
            "submitted_at",
            "reviewed_at",
            "feedback",
            "marks_awarded",
        ]
        read_only_fields = ["id", "status", "reviewed_at", "feedback", "marks_awarded"]

    def get_file_url(self, obj: AssignmentSubmission):
        return _file_url(obj.file, self.context)


class AssignmentSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_color = serializers.CharField(source="subject.color_token", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True, default="")
    class_name = serializers.CharField(source="class_room.display_name", read_only=True)
    attachment_url = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    max_marks = serializers.FloatField(read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id",
            "public_id",
            "title",
            "description",
            "subject",
            "subject_code",
            "subject_name",
            "subject_color",
            "teacher_name",
            "class_name",
            "assigned_on",
            "due_on",
            "max_marks",
            "attachment_url",
            "attachment_name",
            "status",
            "days_remaining",
            "is_overdue",
            "submission",
        ]

    def get_attachment_url(self, obj: Assignment):
        return _file_url(obj.attachment, self.context)

    def get_submission(self, obj: Assignment):
        submission = next(
            (s for s in obj.submissions.all() if s.student_id == self.context.get("student_id")),
            None,
        )
        if submission is None:
            return None
        return AssignmentSubmissionSerializer(submission, context=self.context).data

    def get_status(self, obj: Assignment) -> str:
        submission = next(
            (s for s in obj.submissions.all() if s.student_id == self.context.get("student_id")),
            None,
        )
        if submission is not None:
            return submission.status
        return "NOT_STARTED"

    def get_days_remaining(self, obj: Assignment):
        from datetime import date

        return (obj.due_on - date.today()).days

    def get_is_overdue(self, obj: Assignment) -> bool:
        from datetime import date

        submission = next(
            (s for s in obj.submissions.all() if s.student_id == self.context.get("student_id")),
            None,
        )
        if submission is not None and submission.status in {"SUBMITTED", "REVIEWED", "LATE"}:
            return False
        return obj.due_on < date.today()


class ResourceSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True, default="")
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    subject_color = serializers.CharField(source="subject.color_token", read_only=True, default="sage")
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    class_name = serializers.CharField(source="class_room.display_name", read_only=True, default="")
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True, default="")
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "public_id",
            "title",
            "description",
            "category",
            "category_label",
            "subject",
            "subject_code",
            "subject_name",
            "subject_color",
            "class_name",
            "chapter",
            "academic_year_label",
            "file_url",
            "file_name",
            "file_size",
            "content_type",
            "external_url",
            "is_published",
            "published_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj: Resource):
        return _file_url(obj.file, self.context)

    def get_file_name(self, obj: Resource):
        if obj.file:
            return obj.file.name.rsplit("/", 1)[-1]
        return ""

    def get_file_size(self, obj: Resource):
        from core.models import UploadRecord

        if not obj.file:
            return None
        record = UploadRecord.objects.filter(storage_path=obj.file.name, is_active=True).first()
        return record.size if record else None

    def get_content_type(self, obj: Resource):
        from core.models import UploadRecord

        if not obj.file:
            return None
        record = UploadRecord.objects.filter(storage_path=obj.file.name, is_active=True).first()
        return record.content_type if record else None


class AnnouncementSerializer(serializers.ModelSerializer):
    audience_label = serializers.CharField(source="get_audience_display", read_only=True)
    campus_name = serializers.CharField(source="campus.name", read_only=True, default="")
    class_name = serializers.CharField(source="class_room.display_name", read_only=True, default="")
    section_name = serializers.CharField(source="section.name", read_only=True, default="")
    program_name = serializers.CharField(source="program.name", read_only=True, default="")
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True, default="")
    author_name = serializers.CharField(source="created_by.full_name", read_only=True, default="TEL")
    attachment_url = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "public_id",
            "title",
            "body",
            "audience",
            "audience_label",
            "campus_name",
            "program_name",
            "class_name",
            "section_name",
            "academic_year_label",
            "author_name",
            "attachment_url",
            "attachment_name",
            "is_pinned",
            "published_at",
            "expires_at",
            "is_expired",
        ]
        read_only_fields = fields

    def get_attachment_url(self, obj: Announcement):
        return _file_url(obj.attachment, self.context)

    def get_is_expired(self, obj: Announcement) -> bool:
        from django.utils import timezone

        return bool(obj.expires_at and obj.expires_at < timezone.now())


class AcademicEventSerializer(serializers.ModelSerializer):
    event_type_label = serializers.CharField(source="get_event_type_display", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    subject_color = serializers.CharField(source="subject.color_token", read_only=True, default="sage")
    campus_name = serializers.CharField(source="campus.name", read_only=True, default="")

    class Meta:
        model = AcademicEvent
        fields = [
            "id",
            "public_id",
            "title",
            "description",
            "event_type",
            "event_type_label",
            "starts_at",
            "ends_at",
            "is_all_day",
            "subject_name",
            "subject_color",
            "campus_name",
        ]
        read_only_fields = fields


class StudentRequestSerializer(serializers.ModelSerializer):
    request_type_label = serializers.CharField(source="get_request_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    attachment_url = serializers.SerializerMethodField()
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    responded_by_name = serializers.CharField(source="responded_by.full_name", read_only=True, default="")

    class Meta:
        model = StudentRequest
        fields = [
            "id",
            "ticket_id",
            "request_type",
            "request_type_label",
            "subject_line",
            "description",
            "related_date",
            "attachment_url",
            "attachment_name",
            "status",
            "status_label",
            "admin_response",
            "responded_by_name",
            "responded_at",
            "created_at",
            "updated_at",
            "student_name",
            "student_code",
        ]
        read_only_fields = [
            "id", "ticket_id", "status", "status_label", "admin_response",
            "responded_by_name", "responded_at", "created_at", "updated_at",
            "student_name", "student_code",
        ]

    def get_attachment_url(self, obj: StudentRequest):
        return _file_url(obj.attachment, self.context)


class StudentRequestCreateSerializer(serializers.Serializer):
    request_type = serializers.ChoiceField(choices=RequestType.choices)
    subject_line = serializers.CharField(max_length=180)
    description = serializers.CharField()
    related_date = serializers.DateField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, allow_null=True)

    def validate_description(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 20:
            raise serializers.ValidationError(
                "Please describe the issue in at least 20 characters so TEL can act on it."
            )
        if len(cleaned) > 4000:
            raise serializers.ValidationError("Please keep the description under 4000 characters.")
        return cleaned

    def validate_subject_line(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Give the request a short, clear title.")
        return cleaned


class FeedbackSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Feedback
        fields = [
            "id",
            "category",
            "category_label",
            "rating",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at", "category_label"]


class FeedbackCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=["PORTAL", "RESOURCES", "COMMUNICATION", "TIMETABLE", "OTHER"]
    )
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    message = serializers.CharField()

    def validate_message(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 15:
            raise serializers.ValidationError(
                "Please share at least a sentence so your feedback is useful."
            )
        return cleaned


class ReferenceListsView(serializers.Serializer):
    """Documentation helper listing the choice sets the frontend renders."""

    request_types = [{"value": v, "label": l} for v, l in RequestType.choices]
    request_statuses = [{"value": v, "label": l} for v, l in RequestStatus.choices]
    resource_categories = [{"value": v, "label": l} for v, l in ResourceCategory.choices]
