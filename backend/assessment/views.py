from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import ClassRoom, Section
from academics.selectors import resolve_student_scope
from accounts.models import Role, StudentProfile
from assessment import analytics, practice, services
from assessment.models import (
    ExamType,
    Paper,
    PaperQuestion,
    PaperStatus,
    PracticeAttempt,
    Result,
    ResultStatus,
)
from assessment.serializers import (
    PaperDetailSerializer,
    PaperListSerializer,
    PaperQuestionWriteSerializer,
    PracticeQuestionSerializer,
    PracticeSessionSerializer,
    PaperWriteSerializer,
    ResultMutationSerializer,
    ResultSerializer,
    ResultTransitionSerializer,
)
from common.exceptions import TelAPIException, Forbidden
from common.pagination import TelPagination
from common.uploads import validate_upload
from core.audit import log_event
from core.models import UploadRecord


def _is_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.role in {Role.ADMIN, Role.TEACHER} or user.is_superuser))


def _attempt_map(papers, student):
    rows = (
        PracticeAttempt.objects.filter(paper__in=papers, student=student)
        .order_by("submitted_at", "started_at")
    )
    grouped: dict[int, list] = defaultdict(list)
    for row in rows:
        grouped[row.paper_id].append(row)
    return grouped


# ---------------------------------------------------------------------------
# Papers / practice archive
# ---------------------------------------------------------------------------


class PaperListView(APIView):
    """Staff-facing paper register with the full lifecycle visible."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Use /api/student/papers/ to browse the archive.")
        params = request.query_params
        qs = Paper.objects.select_related(
            "subject", "class_room", "section", "campus", "academic_year", "teacher"
        )
        if params.get("campus"):
            qs = qs.filter(campus_id=params["campus"])
        if params.get("class"):
            qs = qs.filter(class_room_id=params["class"])
        if params.get("section"):
            qs = qs.filter(section_id=params["section"])
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        if params.get("subject"):
            qs = qs.filter(Q(subject_id=params["subject"]) | Q(subject__code__iexact=params["subject"]))
        if params.get("type"):
            qs = qs.filter(exam_type__in=params["type"].split(","))
        if params.get("year"):
            qs = qs.filter(academic_year_id=params["year"])
        if params.get("from"):
            qs = qs.filter(exam_date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(exam_date__lte=params["to"])
        if params.get("teacher"):
            qs = qs.filter(teacher_id=params["teacher"])

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(subject__name__icontains=search)
                | Q(subject__code__icontains=search)
                | Q(instructions__icontains=search)
            )

        qs = qs.annotate(question_count=Count("questions", distinct=True))
        ordering = params.get("ordering")
        if ordering not in {
            "-exam_date", "exam_date", "title", "-created_at", "created_at", "total_marks",
        }:
            ordering = "-exam_date"

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by(ordering), request, view=self)
        return paginator.get_paginated_response(
            PaperListSerializer(page, many=True, context={"request": request}).data
        )


class StudentPaperListView(APIView):
    """Paper archive scoped to the signed-in student, with attempt context."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        student = scope.profile
        params = request.query_params

        qs = (
            Paper.objects.visible_to_students()
            .filter(
                class_room_id=scope.class_id,
                academic_year_id=scope.academic_year_id,
            )
            .select_related("subject", "class_room", "section", "campus", "academic_year", "teacher")
            .annotate(question_count=Count("questions", distinct=True))
        )
        qs = qs.filter(Q(section_id=scope.section_id) | Q(section__isnull=True))

        if params.get("subject"):
            qs = qs.filter(
                Q(subject_id=params["subject"]) | Q(subject__code__iexact=params["subject"])
            )
        if params.get("type"):
            qs = qs.filter(exam_type__in=params["type"].split(","))
        if params.get("year"):
            qs = qs.filter(academic_year_id=params["year"])
        if params.get("from"):
            qs = qs.filter(exam_date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(exam_date__lte=params["to"])

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(subject__name__icontains=search)
                | Q(subject__code__icontains=search)
            )

        ordering = params.get("ordering") if params.get("ordering") in {
            "-exam_date", "exam_date", "title", "-created_at", "created_at"
        } else "-exam_date"

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by(ordering), request, view=self)
        context = {"request": request, "attempts_by_paper": _attempt_map(page, student)}
        return paginator.get_paginated_response(
            PaperListSerializer(page, many=True, context=context).data
        )


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        scope = resolve_student_scope(request.user, required=False)
        paper = (
            Paper.objects.select_related(
                "subject", "class_room", "section", "campus", "academic_year", "teacher"
            )
            .filter(pk=pk)
            .annotate(question_count=Count("questions", distinct=True))
            .first()
        )
        if paper is None:
            raise NotFound("That paper could not be found.")

        if not _is_staff(request.user):
            if scope is None or not paper.is_visible_to_students:
                raise NotFound("That paper could not be found.")
            if paper.class_room_id != scope.class_id:
                # Do not disclose the existence of another class's paper.
                raise NotFound("That paper could not be found.")

        attempts = _attempt_map([paper], scope.profile) if scope else {}
        context = {"request": request, "attempts_by_paper": attempts}
        return Response(PaperDetailSerializer(paper, context=context).data)


class StartPracticeView(APIView):
    """Starts or resumes an attempt and returns the runnable session."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        scope = resolve_student_scope(request.user)
        paper = Paper.objects.filter(pk=pk).select_related(
            "subject", "class_room", "section", "campus", "academic_year"
        ).first()
        if paper is None or not paper.is_visible_to_students:
            raise NotFound("That paper could not be found.")
        if paper.class_room_id != scope.class_id:
            raise NotFound("That paper could not be found.")

        attempt, created = practice.start_attempt(paper=paper, student=scope.profile)
        log_event(
            request, action="practice.started", user=request.user, entity=attempt,
            summary=f"{paper.title} attempt {attempt.attempt_number}",
        )
        payload = {
            "attempt": attempt,
            "paper": paper,
            "questions": PaperQuestion.objects.filter(paper=paper).order_by("order", "id"),
            "resumed": not created,
        }
        return Response(PracticeSessionSerializer(payload, context={"request": request}).data)


class SavePracticeProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        attempt = _own_attempt(request, pk)
        answers = request.data.get("answers")
        if not isinstance(answers, list):
            raise TelAPIException("Send the answers as a list.")
        practice.save_answers(attempt=attempt, answers=answers)
        return Response({"saved": len(answers), "saved_at": attempt.last_saved_at})


class SubmitPracticeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        attempt = _own_attempt(request, pk)
        if request.data.get("answers") is not None:
            if not isinstance(request.data["answers"], list):
                raise TelAPIException("Send the answers as a list.")
            practice.save_answers(attempt=attempt, answers=request.data["answers"])
        attempt = practice.submit_attempt(attempt=attempt)
        log_event(
            request, action="practice.submitted", user=request.user, entity=attempt,
            summary=f"{attempt.paper.title} attempt {attempt.attempt_number} scored {attempt.score}/{attempt.total_marks}",
            metadata={
                "percentage": float(attempt.percentage) if attempt.percentage is not None else None,
                "manual_review": attempt.manual_review_count,
            },
        )
        return Response(PracticeResultPayload(attempt, request).as_dict())


class PracticeReviewView(APIView):
    """Answer key + explanation, released only after submission."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        attempt = _own_attempt(request, pk)
        if not attempt.is_complete:
            raise TelAPIException("Submit the attempt before viewing the answer key.")
        if not attempt.paper.show_answers_after_submit:
            raise TelAPIException("The answer key for this paper is not published.")
        return Response(
            {
                "review": practice.build_review(attempt),
                "message": (
                    "Subjective answers are recorded and pending teacher review; they are "
                    "not included in the auto-graded score."
                    if attempt.manual_review_count
                    else ""
                ),
            }
        )


class PracticeHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        qs = (
            PracticeAttempt.objects.filter(student=scope.profile)
            .select_related("paper", "paper__subject")
            .order_by("-started_at")
        )
        if request.query_params.get("paper"):
            qs = qs.filter(paper_id=request.query_params["paper"])
        if request.query_params.get("status"):
            qs = qs.filter(status__in=request.query_params["status"].split(","))

        grouped: dict[str, list] = defaultdict(list)
        for attempt in qs[:200]:
            grouped[str(attempt.paper_id)].append(
                {
                    "id": attempt.id,
                    "attempt_number": attempt.attempt_number,
                    "score": float(attempt.score),
                    "total_marks": float(attempt.total_marks),
                    "percentage": float(attempt.percentage) if attempt.percentage is not None else None,
                    "status": attempt.status,
                    "submitted_at": attempt.submitted_at,
                    "time_taken_seconds": attempt.time_taken_seconds,
                }
            )

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        history = []
        for attempt in page:
            attempts = sorted(grouped.get(str(attempt.paper_id), []), key=lambda a: a["attempt_number"])
            current = next((a for a in attempts if a["id"] == attempt.id), None)
            previous = [
                a for a in attempts
                if a["attempt_number"] < attempt.attempt_number and a["percentage"] is not None
            ]
            history.append(
                {
                    "attempt_id": attempt.id,
                    "paper_id": attempt.paper_id,
                    "paper_title": attempt.paper.title,
                    "subject_code": attempt.paper.subject.code,
                    "subject_name": attempt.paper.subject.name,
                    "subject_color": attempt.paper.subject.color_token,
                    "exam_type_label": attempt.paper.get_exam_type_display(),
                    "attempts": attempts,
                    "attempt_number": attempt.attempt_number,
                    "score": current["score"] if current else 0,
                    "total_marks": current["total_marks"] if current else 0,
                    "percentage": current["percentage"] if current else None,
                    "status": attempt.status,
                    "submitted_at": attempt.submitted_at,
                    "time_taken_seconds": attempt.time_taken_seconds,
                    "improvement": (
                        round(
                            current["percentage"]
                            - max(a["percentage"] for a in previous),
                            1,
                        )
                        if current and current["percentage"] is not None and previous else None
                    ),
                }
            )
        return paginator.get_paginated_response(history)


def _own_attempt(request, pk: int) -> PracticeAttempt:
    scope = resolve_student_scope(request.user, required=False)
    attempt = (
        PracticeAttempt.objects.select_related("paper", "paper__subject")
        .filter(pk=pk)
        .first()
    )
    if attempt is None:
        raise NotFound("That attempt could not be found.")
    if scope is None or attempt.student_id != scope.student_id:
        # A student can only ever reach their own attempts.
        raise NotFound("That attempt could not be found.")
    return attempt


class PracticeResultPayload:
    """Shapes the post-submission summary shown in the UI."""

    def __init__(self, attempt: PracticeAttempt, request):
        self.attempt = attempt
        self.request = request

    def as_dict(self) -> dict:
        from assessment.practice import grade_for

        attempt = self.attempt
        return {
            "attempt_id": attempt.id,
            "paper_id": attempt.paper_id,
            "paper_title": attempt.paper.title,
            "subject": attempt.paper.subject.name,
            "attempt_number": attempt.attempt_number,
            "score": float(attempt.score),
            "total_marks": float(attempt.total_marks),
            "percentage": float(attempt.percentage) if attempt.percentage is not None else None,
            "grade": grade_for(float(attempt.percentage) if attempt.percentage is not None else None),
            "correct": attempt.correct_count,
            "incorrect": attempt.incorrect_count,
            "unanswered": attempt.unanswered_count,
            "pending_review": attempt.manual_review_count,
            "time_taken_seconds": attempt.time_taken_seconds,
            "has_answer_key": attempt.paper.has_answer_key,
            "notes": (
                "Subjective answers were recorded and sent for teacher review. The score "
                "shown covers auto-graded questions only."
                if attempt.manual_review_count
                else ""
            ),
        }


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class StudentResultListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        qs = (
            Result.objects.visible_to_students()
            .filter(student=scope.profile)
            .select_related("subject", "paper")
            .prefetch_related("items")
            .order_by("-assessment_date", "-created_at")
        )
        params = request.query_params
        if params.get("subject"):
            qs = qs.filter(subject_id=params["subject"])
        if params.get("type"):
            qs = qs.filter(assessment_type__in=params["type"].split(","))
        if params.get("year"):
            qs = qs.filter(
                paper__academic_year_id=params["year"]
            ) | qs.filter(paper__isnull=True)
        if params.get("from"):
            qs = qs.filter(assessment_date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(assessment_date__lte=params["to"])

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(ResultSerializer(page, many=True).data)


class StudentAnalyticsView(APIView):
    """Subject performance, weak subject detection and topic coverage."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings

        scope = resolve_student_scope(request.user)
        student = scope.profile
        subjects = analytics.subject_performance(student)
        weak = analytics.detect_weak_subjects(student)
        return Response(
            {
                "has_results": bool(subjects),
                "message": (
                    ""
                    if subjects
                    else "No published results yet. Subject analysis appears once TEL releases a result."
                ),
                "overall_average": analytics.overall_average(student),
                "subjects": [analytics.asdict_row(s) for s in subjects],
                "weak_subjects": [analytics.asdict_row(w) for w in weak],
                "thresholds": {
                    "weak_subject_score": settings.TEL_WEAK_SUBJECT_SCORE,
                    "weak_subject_min_attempts": settings.TEL_WEAK_SUBJECT_MIN_ATTEMPTS,
                    "attendance_target": settings.TEL_ATTENDANCE_TARGET,
                },
            }
        )


class TopicAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        subject_id = request.query_params.get("subject")
        return Response(analytics.topic_analysis(scope.profile, int(subject_id) if subject_id else None))


class ProgressSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        return Response(analytics.progress_summary(scope.profile))


# ---------------------------------------------------------------------------
# Staff / admin surface
# ---------------------------------------------------------------------------


class ManagePaperCreateView(APIView):
    """Creates a paper record. Reused by the TEL core integration adapter."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        if not _is_staff(request.user) and request.user.role != Role.CLASS_REPRESENTATIVE:
            raise Forbidden("Only TEL staff can create papers.")
        serializer = PaperWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from academics.models import Subject

        class_room = ClassRoom.objects.filter(pk=data["class_id"]).first()
        subject = Subject.objects.filter(pk=data["subject_id"]).first()
        if class_room is None or subject is None:
            raise TelAPIException("Choose a valid class and subject.")
        section = (
            Section.objects.filter(pk=data.get("section_id"), class_room=class_room).first()
            if data.get("section_id")
            else None
        )

        paper = Paper.objects.create(
            title=data["title"][:200],
            subject=subject,
            class_room=class_room,
            section=section,
            campus=class_room.campus,
            academic_year=class_room.academic_year,
            exam_type=data["exam_type"],
            total_marks=int(data["total_marks"]),
            duration_minutes=data.get("duration_minutes", 30),
            exam_date=data.get("exam_date"),
            instructions=data.get("instructions", ""),
            teacher=request.user if _is_staff(request.user) else None,
            status=PaperStatus.VERIFIED if _is_staff(request.user) else PaperStatus.DRAFT,
            source=Paper.Source.PORTAL,
            external_ref=data.get("source_ref", "")[:120],
        )
        if _is_staff(request.user):
            paper.verified_by = request.user
            paper.verified_at = timezone.now()
            paper.save(update_fields=["verified_by", "verified_at"])

        _handle_paper_files(request, paper)
        log_event(request, action="paper.created", user=request.user, entity=paper, summary=paper.title)
        return Response(PaperDetailSerializer(paper, context={"request": request}).data, status=201)


def _handle_paper_files(request, paper: Paper) -> None:
    from core.models import UploadRecord as _UploadRecord

    fields = {
        "paper_file": (_UploadRecord.Purpose.PAPER, "paper"),
        "answer_key_file": (_UploadRecord.Purpose.PAPER, "answer_key"),
    }
    for field, (purpose, label) in fields.items():
        uploaded = request.FILES.get(field)
        if not uploaded:
            continue
        validated = validate_upload(uploaded, field=field)
        setattr(paper, field, validated.storage_name)
        _UploadRecord.objects.create(
            uploader=request.user,
            purpose=purpose,
            storage_path=validated.storage_name,
            original_name=validated.original_name,
            content_type=validated.content_type,
            size=validated.size,
            checksum=validated.checksum,
            visibility=_UploadRecord.Visibility.PUBLISHED,
            class_room=paper.class_room,
            section=paper.section,
        )
    paper.save(update_fields=["paper_file", "answer_key_file"])


class ManagePaperQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        paper = Paper.objects.filter(pk=pk).first()
        if paper is None:
            raise NotFound("That paper could not be found.")
        if not _is_staff(request.user) and request.user.role != Role.CLASS_REPRESENTATIVE:
            raise Forbidden("Only TEL staff can add questions.")

        rows = request.data.get("questions")
        if not isinstance(rows, list) or not rows:
            raise TelAPIException("Send a non-empty list of questions.")

        created = []
        order = paper.questions.count()
        for raw in rows:
            serializer = PaperQuestionWriteSerializer(data=raw)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            order += 1
            created.append(
                PaperQuestion.objects.create(
                    paper=paper,
                    order=order,
                    question_type=data["question_type"],
                    text=data["text"],
                    options=data.get("options") or [],
                    marks=data.get("marks", 1),
                    chapter=data.get("chapter", ""),
                    topic=data.get("topic", ""),
                    correct_option=data.get("correct_option"),
                    answer_key_text=data.get("answer_key_text", ""),
                    explanation=data.get("explanation", ""),
                )
            )
        log_event(
            request, action="paper.questions_added", user=request.user, entity=paper,
            metadata={"count": len(created)},
        )
        return Response(
            PracticeQuestionSerializer(created, many=True).data, status=status.HTTP_201_CREATED
        )


class ManagePaperTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        paper = Paper.objects.filter(pk=pk).first()
        if paper is None:
            raise NotFound("That paper could not be found.")
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can change a paper's state.")
        target = (request.data.get("status") or "").strip().upper()
        if target not in services.PAPER_TRANSITIONS:
            raise TelAPIException("Choose a valid target state.")
        release_at = request.data.get("release_at")
        services.transition_paper(
            paper=paper, target=target, actor=request.user, release_at=release_at or None
        )
        return Response(PaperDetailSerializer(paper, context={"request": request}).data)


class ManageResultListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can browse the result register.")
        qs = Result.objects.select_related("student", "subject", "paper")
        params = request.query_params
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        if params.get("class"):
            qs = qs.filter(student__class_room_id=params["class"])
        if params.get("student"):
            qs = qs.filter(student_id=params["student"])
        try:
            limit = min(int(params.get("limit", 50)), 200)
        except (TypeError, ValueError):
            limit = 50
        return Response(
            {"count": qs.count(), "results": ResultSerializer(qs[:limit], many=True).data}
        )

    def post(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can enter results.")
        serializer = ResultMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from academics.models import Subject

        student = StudentProfile.objects.filter(
            pk=data["student_id"], status=StudentProfile.Status.ACTIVE
        ).first()
        subject = Subject.objects.filter(pk=data["subject_id"]).first()
        if student is None or subject is None:
            raise TelAPIException("Choose a valid student and subject.")
        paper = Paper.objects.filter(pk=data.get("paper_id")).first() if data.get("paper_id") else None

        result = services.create_result(
            student=student, subject=subject, paper=paper, data=data, actor=request.user
        )
        return Response(ResultSerializer(result).data, status=status.HTTP_201_CREATED)


class ManageResultTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can change a result's state.")
        result = Result.objects.filter(pk=pk).first()
        if result is None:
            raise NotFound("That result could not be found.")
        serializer = ResultTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.transition_result(
            result=result,
            target=serializer.validated_data["status"],
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(ResultSerializer(result).data)


class ExamTypeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            [{"value": value, "label": label} for value, label in ExamType.choices]
        )


class StudentRegisterView(APIView):
    """
    Minimal student register used by the result-entry form.

    Restricted to TEL staff and scoped to their campus so it cannot be used to
    enumerate the student body.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can browse the student register.")
        qs = StudentProfile.objects.select_related("user", "class_room", "section", "campus")
        if request.user.role == Role.TEACHER:
            campus = getattr(getattr(request.user, "teacher_profile", None), "campus", None)
            if campus:
                qs = qs.filter(campus=campus)
        if request.query_params.get("class"):
            qs = qs.filter(class_room_id=request.query_params["class"])
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(user__full_name__icontains=search) | Q(student_code__icontains=search)
            )
        results = [
            {
                "id": p.id,
                "student_code": p.student_code,
                "name": p.user.full_name,
                "class_name": p.class_room.display_name if p.class_room else "",
                "section_name": p.section.name if p.section else "",
            }
            for p in qs[:50]
        ]
        return Response({"count": len(results), "results": results})


class ResultStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{"value": s.value, "label": s.label} for s in ResultStatus])
