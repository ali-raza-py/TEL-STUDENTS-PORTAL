from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from assessment.models import (
    ExamType,
    Paper,
    PaperQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Result,
    ResultItem,
    ResultStatus,
)


def _file_url(record_field: str, context) -> str | None:
    """Files are streamed through the authorised file view, never a raw path."""

    request = context.get("request")
    value = record_field
    if not value:
        return None
    from core.models import UploadRecord

    record = UploadRecord.objects.filter(storage_path=value.name, is_active=True).first()
    if record is None:
        return None
    path = f"/api/files/{record.pk}/"
    return request.build_absolute_uri(path) if request else path


class PaperListSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_color = serializers.CharField(source="subject.color_token", read_only=True)
    exam_type_label = serializers.CharField(source="get_exam_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    class_name = serializers.CharField(source="class_room.display_name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True, default="")
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True, default="")
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)
    question_count = serializers.IntegerField(read_only=True, default=0)
    attempt_count = serializers.IntegerField(read_only=True, default=0)
    best_attempt_percentage = serializers.SerializerMethodField()
    latest_attempt_percentage = serializers.SerializerMethodField()
    attempts_remaining = serializers.SerializerMethodField()
    can_practice = serializers.SerializerMethodField()
    has_paper_file = serializers.SerializerMethodField()
    visibility_scope = serializers.CharField(read_only=True)
    visibility_scope_label = serializers.CharField(
        source="get_visibility_scope_display", read_only=True
    )
    shared_campuses = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = [
            "id",
            "public_id",
            "title",
            "exam_type",
            "exam_type_label",
            "status",
            "status_label",
            "subject",
            "subject_code",
            "subject_name",
            "subject_color",
            "class_room",
            "class_name",
            "section",
            "section_name",
            "campus",
            "campus_name",
            "academic_year",
            "academic_year_label",
            "teacher_name",
            "total_marks",
            "duration_minutes",
            "exam_date",
            "published_at",
            "question_count",
            "attempt_count",
            "best_attempt_percentage",
            "latest_attempt_percentage",
            "attempts_remaining",
            "can_practice",
            "has_answer_key",
            "has_topic_metadata",
            "has_paper_file",
            "allow_retake",
            "attempt_limit",
            "visibility_scope",
            "visibility_scope_label",
            "shared_campuses",
        ]

    def get_shared_campuses(self, obj: Paper):
        if obj.visibility_scope != "SELECTED_CAMPUSES":
            return []
        return [
            {"id": c.campus_id, "name": c.campus.name}
            for c in obj.shared_campuses.select_related("campus").all()
        ]

    def _attempts(self, obj: Paper):
        cache = self.context.get("attempts_by_paper")
        if cache is None:
            return None
        return cache.get(obj.id)

    def get_best_attempt_percentage(self, obj: Paper):
        attempts = self._attempts(obj)
        if not attempts:
            return None
        values = [float(a.percentage) for a in attempts if a.percentage is not None]
        return round(max(values), 1) if values else None

    def get_latest_attempt_percentage(self, obj: Paper):
        attempts = self._attempts(obj)
        if not attempts:
            return None
        latest = max(attempts, key=lambda a: a.submitted_at or a.started_at)
        return float(latest.percentage) if latest.percentage is not None else None

    def get_attempts_remaining(self, obj: Paper):
        attempts = self._attempts(obj)
        if not obj.allow_retake or not obj.attempt_limit:
            return None
        if attempts is None:
            return None
        return max(0, obj.attempt_limit - len(attempts))

    def get_can_practice(self, obj: Paper) -> bool:
        return bool(obj.is_practice_enabled)

    def get_has_paper_file(self, obj: Paper) -> bool:
        return bool(obj.paper_file)


class PaperDetailSerializer(PaperListSerializer):
    """Adds the paper document link and, for staff, the lifecycle controls."""

    paper_file_url = serializers.SerializerMethodField()
    answer_key_file_url = serializers.SerializerMethodField()
    instructions = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    external_ref = serializers.CharField(read_only=True)
    attempts = serializers.SerializerMethodField()

    class Meta(PaperListSerializer.Meta):
        fields = PaperListSerializer.Meta.fields + [
            "instructions",
            "paper_file_url",
            "answer_key_file_url",
            "source",
            "external_ref",
            "attempts",
        ]

    def get_paper_file_url(self, obj: Paper):
        return _file_url(obj.paper_file, self.context)

    def get_answer_key_file_url(self, obj: Paper):
        return _file_url(obj.answer_key_file, self.context)

    def get_attempts(self, obj: Paper):
        attempts = self._attempts(obj)
        if attempts is None:
            return []
        return [
            {
                "id": a.id,
                "attempt_number": a.attempt_number,
                "status": a.status,
                "score": float(a.score),
                "total_marks": float(a.total_marks),
                "percentage": float(a.percentage) if a.percentage is not None else None,
                "submitted_at": a.submitted_at,
            }
            for a in sorted(attempts, key=lambda a: a.attempt_number)
        ]


class PracticeQuestionSerializer(serializers.ModelSerializer):
    """Question payload for an active attempt.

    ``correct_option`` is deliberately absent — the answer key is released only
    after submission through the review endpoint.
    """

    options = serializers.JSONField(read_only=True)
    marks = serializers.FloatField(read_only=True)

    class Meta:
        model = PaperQuestion
        fields = ["id", "order", "question_type", "text", "options", "marks", "chapter"]


class PracticeAnswerSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField()

    class Meta:
        model = PracticeAnswer
        fields = ["question_id", "selected_option", "text_answer"]


class PracticeAttemptSerializer(serializers.ModelSerializer):
    paper_title = serializers.CharField(source="paper.title", read_only=True)
    subject_name = serializers.CharField(source="paper.subject.name", read_only=True)
    subject_code = serializers.CharField(source="paper.subject.code", read_only=True)
    subject_color = serializers.CharField(source="paper.subject.color_token", read_only=True)
    exam_type_label = serializers.CharField(source="paper.get_exam_type_display", read_only=True)
    score = serializers.FloatField(read_only=True)
    total_marks = serializers.FloatField(read_only=True)
    percentage = serializers.FloatField(read_only=True, allow_null=True)
    accuracy = serializers.FloatField(read_only=True, allow_null=True)
    grade = serializers.SerializerMethodField()
    has_pending_review = serializers.SerializerMethodField()

    class Meta:
        model = PracticeAttempt
        fields = [
            "id",
            "public_id",
            "paper",
            "paper_title",
            "subject_name",
            "subject_code",
            "subject_color",
            "exam_type_label",
            "attempt_number",
            "status",
            "started_at",
            "submitted_at",
            "time_taken_seconds",
            "score",
            "total_marks",
            "percentage",
            "accuracy",
            "grade",
            "correct_count",
            "incorrect_count",
            "unanswered_count",
            "manual_review_count",
            "has_pending_review",
        ]

    def get_grade(self, obj: PracticeAttempt) -> str:
        from assessment.practice import grade_for

        return grade_for(float(obj.percentage) if obj.percentage is not None else None)

    def get_has_pending_review(self, obj: PracticeAttempt) -> bool:
        return obj.manual_review_count > 0


class PracticeSessionSerializer(serializers.Serializer):
    """Everything the practice runner needs to start."""

    attempt_id = serializers.SerializerMethodField()
    paper = PaperDetailSerializer(read_only=True)
    questions = PracticeQuestionSerializer(many=True, read_only=True)
    saved_answers = serializers.SerializerMethodField()
    attempt_number = serializers.SerializerMethodField()
    started_at = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()

    def get_attempt_id(self, obj) -> int:
        return obj["attempt"].id

    def get_attempt_number(self, obj) -> int:
        return obj["attempt"].attempt_number

    def get_started_at(self, obj):
        return obj["attempt"].started_at

    def get_saved_answers(self, obj) -> list[dict]:
        return [
            {
                "question_id": answer.question_id,
                "selected_option": answer.selected_option,
                "text_answer": answer.text_answer,
            }
            for answer in obj["attempt"].answers.select_related("question").all()
        ]

    def get_time_remaining_seconds(self, obj) -> int | None:
        from django.utils import timezone

        paper = obj["paper"]
        if not paper.duration_minutes:
            return None
        elapsed = int((timezone.now() - obj["attempt"].started_at).total_seconds())
        return max(0, paper.duration_minutes * 60 - elapsed)

    def get_resume(self, obj) -> bool:
        return bool(obj.get("resumed"))


class ResultItemSerializer(serializers.ModelSerializer):
    marks_awarded = serializers.FloatField(read_only=True)
    marks_total = serializers.FloatField(read_only=True)

    class Meta:
        model = ResultItem
        fields = ["id", "question_label", "chapter", "topic", "marks_awarded", "marks_total"]


class ResultSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_color = serializers.CharField(source="subject.color_token", read_only=True)
    assessment_type_label = serializers.CharField(source="get_assessment_type_display", read_only=True)
    obtained_marks = serializers.FloatField(read_only=True)
    total_marks = serializers.FloatField(read_only=True)
    percentage = serializers.FloatField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    paper_title = serializers.CharField(source="paper.title", read_only=True, default="")
    # Who the result belongs to. The staff register is unusable without this —
    # a result row that cannot be attributed to a student is not a record.
    student_name = serializers.CharField(
        source="student.user.full_name", read_only=True, default=""
    )
    student_code = serializers.CharField(source="student.student_code", read_only=True, default="")
    class_name = serializers.CharField(
        source="student.class_room.display_name", read_only=True, default=""
    )
    section_name = serializers.CharField(source="student.section.name", read_only=True, default="")
    items = ResultItemSerializer(many=True, read_only=True)
    has_topic_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            "id",
            "student",
            "student_name",
            "student_code",
            "class_name",
            "section_name",
            "assessment_name",
            "assessment_type",
            "assessment_type_label",
            "assessment_date",
            "subject",
            "subject_code",
            "subject_name",
            "subject_color",
            "paper",
            "paper_title",
            "obtained_marks",
            "total_marks",
            "percentage",
            "grade",
            "position_in_class",
            "remarks",
            "status",
            "status_label",
            "published_at",
            "items",
            "has_topic_breakdown",
        ]

    def get_has_topic_breakdown(self, obj: Result) -> bool:
        return any(item.topic for item in obj.items.all())


class ResultMutationSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    paper_id = serializers.IntegerField(required=False, allow_null=True)
    subject_id = serializers.IntegerField()
    assessment_name = serializers.CharField(max_length=200)
    assessment_type = serializers.ChoiceField(choices=ExamType.choices)
    assessment_date = serializers.DateField()
    total_marks = serializers.FloatField(min_value=0.01)
    obtained_marks = serializers.FloatField(min_value=0)
    grade = serializers.CharField(max_length=8, required=False, allow_blank=True)
    position_in_class = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    remarks = serializers.CharField(max_length=240, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["obtained_marks"] > attrs["total_marks"]:
            raise serializers.ValidationError(
                {"obtained_marks": "Obtained marks cannot exceed the total."}
            )
        return attrs


class ResultTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ResultStatus.choices)
    note = serializers.CharField(max_length=240, required=False, allow_blank=True)


class PaperWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    subject_id = serializers.IntegerField()
    class_id = serializers.IntegerField()
    section_id = serializers.IntegerField(required=False, allow_null=True)
    exam_type = serializers.ChoiceField(choices=ExamType.choices)
    total_marks = serializers.FloatField(min_value=0.01)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=600, default=30)
    exam_date = serializers.DateField(required=False, allow_null=True)
    instructions = serializers.CharField(required=False, allow_blank=True)
    source_ref = serializers.CharField(max_length=120, required=False, allow_blank=True)


class PaperQuestionWriteSerializer(serializers.Serializer):
    question_type = serializers.ChoiceField(
        choices=["MCQ", "TRUE_FALSE", "SHORT", "SUBJECTIVE"]
    )
    text = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField(), required=False)
    marks = serializers.FloatField(min_value=0.01, default=1)
    chapter = serializers.CharField(max_length=140, required=False, allow_blank=True)
    topic = serializers.CharField(max_length=140, required=False, allow_blank=True)
    correct_option = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    answer_key_text = serializers.CharField(required=False, allow_blank=True)
    explanation = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        qtype = attrs["question_type"]
        options = attrs.get("options") or []
        correct = attrs.get("correct_option")
        if qtype in {"MCQ", "TRUE_FALSE"}:
            if len(options) < 2:
                raise serializers.ValidationError(
                    {"options": "Multiple choice questions need at least two options."}
                )
            if correct is None:
                raise serializers.ValidationError(
                    {"correct_option": "An answer key is required for auto-graded questions."}
                )
            if correct >= len(options):
                raise serializers.ValidationError(
                    {"correct_option": "The answer key points at an option that does not exist."}
                )
        if qtype == "MCQ" and len(options) < 4:
            raise serializers.ValidationError(
                {"options": "Provide four options for a multiple choice question."}
            )
        if qtype not in {"MCQ", "TRUE_FALSE"} and correct is not None:
            raise serializers.ValidationError(
                {"correct_option": "Only objective questions can carry an answer key."}
            )
        return attrs


def decimal_or_none(value: Decimal) -> float | None:
    return float(value) if value is not None else None
