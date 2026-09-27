from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel, UUIDPublicIdModel


class ExamType(models.TextChoices):
    WEEKLY_TEST = "WEEKLY_TEST", "Weekly test"
    MONTHLY_TEST = "MONTHLY_TEST", "Monthly test"
    MIDTERM = "MIDTERM", "Midterm"
    FINAL_EXAM = "FINAL_EXAM", "Final exam"
    MOCK = "MOCK", "Mock exam"
    PRACTICE = "PRACTICE", "Practice paper"
    PAST = "PAST", "Past paper"


EXAM_TYPE_ORDER = {
    ExamType.WEEKLY_TEST: 0,
    ExamType.MONTHLY_TEST: 1,
    ExamType.MIDTERM: 2,
    ExamType.MOCK: 3,
    ExamType.PAST: 4,
    ExamType.FINAL_EXAM: 5,
    ExamType.PRACTICE: 6,
}


class PaperStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    COMPLETED = "COMPLETED", "Completed"
    VERIFIED = "VERIFIED", "Verified"
    PUBLISHED = "PUBLISHED", "Published"
    PRACTICE_AVAILABLE = "PRACTICE_AVAILABLE", "Available for practice"
    ARCHIVED = "ARCHIVED", "Archived"


#: Students only ever see papers in these states.
STUDENT_VISIBLE_PAPER_STATES = {PaperStatus.PUBLISHED, PaperStatus.PRACTICE_AVAILABLE}


class PaperQuerySet(models.QuerySet):
    def visible_to_students(self) -> "PaperQuerySet":
        """Published, not archived, and past its release gate."""
        from django.db.models import Q

        return self.filter(
            Q(status__in=list(STUDENT_VISIBLE_PAPER_STATES)),
            Q(is_archived=False),
            Q(release_at__isnull=True) | Q(release_at__lte=timezone.now()),
        )


class Paper(TimeStampedModel, UUIDPublicIdModel):
    """
    A TEL paper.

    A paper is entered once in TEL core and surfaces in the portal; nothing here
    duplicates teacher data entry. ``source`` records where the record came from
    so the integration layer can be swapped without changing the frontend.
    """

    class Source(models.TextChoices):
        TEL_CORE = "TEL_CORE", "TEL core system"
        PORTAL = "PORTAL", "Student portal"

    title = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=20, choices=ExamType.choices, db_index=True)
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="papers"
    )
    class_room = models.ForeignKey(
        "academics.ClassRoom", on_delete=models.PROTECT, related_name="papers"
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.PROTECT, related_name="papers", null=True, blank=True
    )
    campus = models.ForeignKey(
        "academics.Campus", on_delete=models.PROTECT, related_name="papers"
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.PROTECT, related_name="papers"
    )
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="papers", null=True
    )

    total_marks = models.PositiveSmallIntegerField(default=50)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    instructions = models.TextField(blank=True)

    status = models.CharField(
        max_length=24, choices=PaperStatus.choices, default=PaperStatus.DRAFT, db_index=True
    )
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.PORTAL)
    external_ref = models.CharField(max_length=120, blank=True, db_index=True)

    paper_file = models.FileField(upload_to="papers/%Y/%m/", null=True, blank=True)
    answer_key_file = models.FileField(upload_to="answer-keys/%Y/%m/", null=True, blank=True)

    attempt_limit = models.PositiveSmallIntegerField(default=0)  # 0 = unlimited
    show_answers_after_submit = models.BooleanField(default=True)
    shuffle_questions = models.BooleanField(default=False)
    allow_retake = models.BooleanField(default=True)

    exam_date = models.DateField(null=True, blank=True, db_index=True)
    release_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="papers_verified", null=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    last_synced_from_tel = models.DateTimeField(null=True, blank=True)

    objects = PaperQuerySet.as_manager()

    class Meta:
        ordering = ("-exam_date", "-created_at")
        indexes = [
            models.Index(fields=["class_room", "section", "status"]),
            models.Index(fields=["subject", "exam_type"]),
            models.Index(fields=["academic_year", "exam_date"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.title} ({self.get_exam_type_display()})"

    @property
    def is_visible_to_students(self) -> bool:
        if self.status not in STUDENT_VISIBLE_PAPER_STATES or self.is_archived:
            return False
        if self.release_at and self.release_at > timezone.now():
            return False
        return True

    @property
    def is_practice_enabled(self) -> bool:
        return self.status == PaperStatus.PRACTICE_AVAILABLE and self.questions.exists()

    @property
    def has_answer_key(self) -> bool:
        if self.answer_key_file:
            return True
        return self.questions.filter(
            question_type__in=["MCQ", "TRUE_FALSE"], correct_option__isnull=False
        ).exists()

    @property
    def has_topic_metadata(self) -> bool:
        return self.questions.exclude(topic="").exclude(topic__isnull=True).exists()


class QuestionType(models.TextChoices):
    MCQ = "MCQ", "Multiple choice"
    TRUE_FALSE = "TRUE_FALSE", "True / false"
    SHORT = "SHORT", "Short answer"
    SUBJECTIVE = "SUBJECTIVE", "Subjective"


#: Only these types are graded automatically — everything else needs a teacher.
AUTO_GRADABLE_TYPES = {QuestionType.MCQ, QuestionType.TRUE_FALSE}


class PaperQuestion(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField(default=1)
    question_type = models.CharField(
        max_length=12, choices=QuestionType.choices, default=QuestionType.MCQ
    )
    text = models.TextField()
    options = models.JSONField(default=list, blank=True)  # list[str]
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    # Topic metadata is optional. Analytics that needs it is only shown when the
    # underlying TEL data actually carries it.
    chapter = models.CharField(max_length=140, blank=True)
    topic = models.CharField(max_length=140, blank=True, db_index=True)

    correct_option = models.PositiveSmallIntegerField(null=True, blank=True)
    answer_key_text = models.TextField(blank=True)
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(fields=["paper", "order"], name="uniq_question_order")
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.paper_id} Q{self.order}"

    @property
    def is_auto_gradable(self) -> bool:
        return self.question_type in AUTO_GRADABLE_TYPES and self.correct_option is not None

    @property
    def needs_manual_grading(self) -> bool:
        return not self.is_auto_gradable


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    SUBMITTED = "SUBMITTED", "Submitted"
    GRADED = "GRADED", "Graded"


class PracticeAttemptQuerySet(models.QuerySet):
    def completed(self) -> "PracticeAttemptQuerySet":
        return self.filter(status__in=[AttemptStatus.SUBMITTED, AttemptStatus.GRADED])


class PracticeAttempt(TimeStampedModel, UUIDPublicIdModel):
    """One student's run at one paper. Progress can be saved before submitting."""

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="practice_attempts"
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=12, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS, db_index=True
    )

    started_at = models.DateTimeField(default=timezone.now)
    last_saved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)

    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    correct_count = models.PositiveSmallIntegerField(default=0)
    incorrect_count = models.PositiveSmallIntegerField(default=0)
    unanswered_count = models.PositiveSmallIntegerField(default=0)
    manual_review_count = models.PositiveSmallIntegerField(default=0)
    auto_graded_marks = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    objects = PracticeAttemptQuerySet.as_manager()

    class Meta:
        ordering = ("-started_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["paper", "student", "attempt_number"], name="uniq_attempt_number"
            )
        ]
        indexes = [models.Index(fields=["student", "status"])]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.student.student_code} · {self.paper.title} · attempt {self.attempt_number}"

    @property
    def is_complete(self) -> bool:
        return self.status in {AttemptStatus.SUBMITTED, AttemptStatus.GRADED}

    @property
    def accuracy(self) -> float | None:
        denominator = self.correct_count + self.incorrect_count
        if denominator == 0:
            return None
        return round(self.correct_count / denominator * 100, 1)


class PracticeAnswer(models.Model):
    attempt = models.ForeignKey(PracticeAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(PaperQuestion, on_delete=models.CASCADE, related_name="answers")
    selected_option = models.PositiveSmallIntegerField(null=True, blank=True)
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True)
    marks_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_auto_graded = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="uniq_attempt_answer")
        ]
        indexes = [models.Index(fields=["attempt", "is_correct"])]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class ResultStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted for verification"
    VERIFIED = "VERIFIED", "Verified"
    PUBLISHED = "PUBLISHED", "Published"


class ResultQuerySet(models.QuerySet):
    def visible_to_students(self) -> "ResultQuerySet":
        return self.filter(status=ResultStatus.PUBLISHED, is_revoked=False)


class Result(models.Model):
    """An official TEL assessment result for one student."""

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="results"
    )
    paper = models.ForeignKey(
        Paper, on_delete=models.SET_NULL, related_name="results", null=True, blank=True
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="results"
    )
    assessment_name = models.CharField(max_length=200)
    assessment_type = models.CharField(max_length=20, choices=ExamType.choices, db_index=True)
    assessment_date = models.DateField(db_index=True)

    total_marks = models.DecimalField(max_digits=7, decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=7, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    grade = models.CharField(max_length=8, blank=True)
    position_in_class = models.PositiveSmallIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=240, blank=True)

    status = models.CharField(
        max_length=12, choices=ResultStatus.choices, default=ResultStatus.DRAFT, db_index=True
    )
    is_revoked = models.BooleanField(default=False)

    entered_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="results_entered", null=True
    )
    verified_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="results_verified", null=True
    )
    published_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="results_published", null=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_synced_from_tel = models.DateTimeField(null=True, blank=True)

    objects = ResultQuerySet.as_manager()

    class Meta:
        ordering = ("-assessment_date", "-created_at")
        indexes = [models.Index(fields=["student", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "paper"],
                condition=models.Q(paper__isnull=False),
                name="uniq_result_per_student_paper",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.student.student_code} · {self.assessment_name} · {self.percentage}%"

    def clean(self):
        if self.total_marks and self.obtained_marks is not None:
            if self.obtained_marks > self.total_marks:
                raise ValidationError(
                    {"obtained_marks": "Obtained marks cannot exceed the total."}
                )

    @property
    def is_visible_to_students(self) -> bool:
        return self.status == ResultStatus.PUBLISHED and not self.is_revoked


class ResultItem(models.Model):
    """
    Question or topic level breakdown.

    Populated only when TEL's question data carries topic metadata. Rows with a
    null ``topic`` still allow aggregate marks, and the analytics layer reports
    topic coverage honestly rather than inventing it.
    """

    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="items")
    question_label = models.CharField(max_length=160, blank=True)
    chapter = models.CharField(max_length=140, blank=True)
    topic = models.CharField(max_length=140, blank=True, db_index=True)
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    marks_total = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=["result", "topic"])]


class ResultPublication(models.Model):
    """Records every lifecycle move so a result's history is auditable."""

    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, choices=ResultStatus.choices)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="result_transitions", null=True
    )
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
