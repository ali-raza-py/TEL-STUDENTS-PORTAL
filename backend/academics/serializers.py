from __future__ import annotations

from rest_framework import serializers

from academics.models import (
    AcademicYear,
    Campus,
    ClassRepresentative,
    ClassRoom,
    Program,
    Section,
    Subject,
    SubjectOffering,
    Timetable,
    TimetableEntry,
    TimetableSubmission,
    Weekday,
)


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "code", "name", "address", "phone", "email"]


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ["id", "code", "name", "level", "department"]


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "code", "label", "start_date", "end_date", "is_current", "is_locked"]


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "name", "capacity", "room", "display_name"]


class ClassRoomSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = ClassRoom
        fields = [
            "id",
            "code",
            "name",
            "display_name",
            "program",
            "program_name",
            "campus",
            "campus_name",
            "academic_year",
            "academic_year_label",
            "sections",
        ]


class SubjectSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    teacher_names = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "code",
            "name",
            "program",
            "program_name",
            "kind",
            "credit_hours",
            "is_elective",
            "description",
            "teacher_names",
        ]

    def get_teacher_names(self, obj: Subject) -> list[str]:
        cached = self.context.get("teacher_names")
        if cached is not None:
            return cached.get(obj.id, [])
        return list(
            obj.teachers.filter(is_active=True).values_list("full_name", flat=True)[:5]
        )


class SubjectOfferingSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField(read_only=True)
    subject_code = serializers.CharField(read_only=True)
    subject_name = serializers.CharField(read_only=True)
    subject_kind = serializers.CharField(source="subject.kind", read_only=True)
    teacher_id = serializers.IntegerField(source="teacher_id", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True, default="")
    paper_count = serializers.IntegerField(read_only=True, default=0)
    resource_count = serializers.IntegerField(read_only=True, default=0)


class TimetableEntrySerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_color = serializers.CharField(source="subject.color_token", read_only=True, default="sage")
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True, default="")
    room = serializers.CharField(read_only=True)
    day_label = serializers.SerializerMethodField()
    start_label = serializers.SerializerMethodField()
    end_label = serializers.SerializerMethodField()

    class Meta:
        model = TimetableEntry
        fields = [
            "id",
            "day_of_week",
            "day_label",
            "start_time",
            "end_time",
            "start_label",
            "end_label",
            "subject",
            "subject_code",
            "subject_name",
            "subject_color",
            "teacher_name",
            "room",
            "campus",
            "note",
        ]

    def get_day_label(self, obj: TimetableEntry) -> str:
        return Weekday.label_for(obj.day_of_week)

    def get_start_label(self, obj: TimetableEntry) -> str:
        return f"{obj.start_time:%I:%M %p}".lstrip("0")

    def get_end_label(self, obj: TimetableEntry) -> str:
        return f"{obj.end_time:%I:%M %p}".lstrip("0")


class TimetableSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_room.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    campus_name = serializers.CharField(source="class_room.campus.name", read_only=True)
    version_label = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    entries = TimetableEntrySerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default="")
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Timetable
        fields = [
            "id",
            "public_id",
            "class_room",
            "class_name",
            "section",
            "section_name",
            "campus_name",
            "academic_year",
            "version",
            "version_label",
            "status",
            "status_label",
            "title",
            "effective_from",
            "change_note",
            "source",
            "created_by_name",
            "approved_by_name",
            "approved_at",
            "published_at",
            "archived_at",
            "entries",
            "is_editable",
        ]

    def get_version_label(self, obj: Timetable) -> str:
        return f"Timetable v{obj.version}"

    def get_is_editable(self, obj: Timetable) -> bool:
        return False


class TimetableSubmissionSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_room.display_name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    submitted_by_name = serializers.CharField(
        source="submitted_by.full_name", read_only=True, default=""
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.full_name", read_only=True, default=""
    )
    image_url = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    entry_count = serializers.SerializerMethodField()

    class Meta:
        model = TimetableSubmission
        fields = [
            "id",
            "public_id",
            "class_room",
            "class_name",
            "section",
            "section_name",
            "submitted_by_name",
            "status",
            "status_label",
            "summary",
            "change_note",
            "review_note",
            "reviewed_by_name",
            "reviewed_at",
            "entries_payload",
            "image_url",
            "pdf_url",
            "entry_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj: TimetableSubmission) -> str | None:
        if not obj.image_file:
            return None
        from core.models import UploadRecord

        record = UploadRecord.objects.filter(
            storage_path=obj.image_file.name, is_active=True
        ).first()
        request = self.context.get("request")
        path = f"/api/files/{record.pk}/" if record else None
        return request.build_absolute_uri(path) if request and path else path

    def get_pdf_url(self, obj: TimetableSubmission) -> str | None:
        if not obj.pdf_file:
            return None
        from core.models import UploadRecord

        record = UploadRecord.objects.filter(
            storage_path=obj.pdf_file.name, is_active=True
        ).first()
        request = self.context.get("request")
        path = f"/api/files/{record.pk}/" if record else None
        return request.build_absolute_uri(path) if request and path else path

    def get_entry_count(self, obj: TimetableSubmission) -> int:
        return len(obj.entries_payload or [])


class ClassRepresentativeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    student_code = serializers.CharField(
        source="user.student_profile.student_code", read_only=True, default=""
    )
    class_name = serializers.CharField(source="class_room.display_name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    assigned_by_name = serializers.CharField(
        source="assigned_by.full_name", read_only=True, default=""
    )

    class Meta:
        model = ClassRepresentative
        fields = [
            "id",
            "class_room",
            "class_name",
            "section",
            "section_name",
            "user",
            "user_name",
            "user_email",
            "student_code",
            "assigned_by_name",
            "starts_on",
            "ends_on",
            "is_active",
            "created_at",
        ]


class TimetableSubmissionCreateSerializer(serializers.Serializer):
    class_id = serializers.IntegerField()
    section_id = serializers.IntegerField()
    summary = serializers.CharField(max_length=240, required=False, allow_blank=True)
    change_note = serializers.CharField(required=False, allow_blank=True)
    entries = serializers.ListField(child=serializers.DictField(), required=False)
    image = serializers.FileField(required=False, allow_null=True)
    pdf = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        if not any(
            [
                attrs.get("entries"),
                attrs.get("image"),
                attrs.get("pdf"),
                (attrs.get("summary") or "").strip(),
                (attrs.get("change_note") or "").strip(),
            ]
        ):
            raise serializers.ValidationError(
                "Provide a description, structured entries, or an attachment."
            )
        return attrs
