from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics import services
from academics.models import (
    AcademicYear,
    ClassRepresentative,
    ClassRoom,
    Section,
    SubjectOffering,
    Timetable,
    TimetableStatus,
    TimetableSubmission,
)
from academics.selectors import resolve_student_scope
from academics.serializers import (
    AcademicYearSerializer,
    CampusSerializer,
    ClassRepresentativeSerializer,
    ClassRoomSerializer,
    ProgramSerializer,
    SubjectSerializer,
    TimetableSerializer,
    TimetableSubmissionCreateSerializer,
    TimetableSubmissionSerializer,
)
from accounts.models import Role, User
from common.exceptions import TelAPIException, Forbidden
from common.uploads import validate_upload
from core.audit import log_event
from core.models import UploadRecord


# ---------------------------------------------------------------------------
# Student-facing read API
# ---------------------------------------------------------------------------


def _published_timetable(scope):
    return (
        Timetable.objects.filter(
            class_room_id=scope.class_id,
            section_id=scope.section_id,
            academic_year_id=scope.academic_year_id,
            status=TimetableStatus.PUBLISHED,
        )
        .select_related("class_room", "section", "approved_by")
        .prefetch_related(
            Prefetch("entries", queryset=_entries_queryset())
        )
        .first()
    )


def _entries_queryset():
    from academics.models import TimetableEntry

    return TimetableEntry.objects.select_related("subject", "teacher", "campus").order_by(
        "day_of_week", "start_time"
    )


class StudentClassView(APIView):
    """Class identity used by the header, timetable and subject pages."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        profile = scope.profile
        if profile.class_room is None:
            return Response({"class": None, "sections": []})
        return Response(
            {
                "class": ClassRoomSerializer(profile.class_room).data,
                "sections": [
                    {"id": s.id, "name": s.name, "display_name": s.display_name}
                    for s in profile.class_room.sections.filter(is_active=True)
                ],
                "campus": CampusSerializer(profile.campus).data if profile.campus else None,
                "program": ProgramSerializer(profile.program).data if profile.program else None,
                "academic_year": (
                    AcademicYearSerializer(profile.academic_year).data
                    if profile.academic_year
                    else None
                ),
            }
        )


class SubjectListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        offerings = (
            SubjectOffering.objects.filter(
                class_room_id=scope.class_id,
                academic_year_id=scope.academic_year_id,
                is_active=True,
            )
            .select_related("subject", "subject__program", "teacher")
            .annotate(
                paper_count=Count("subject__papers", filter=Q(subject__papers__status__in=["PUBLISHED", "PRACTICE_AVAILABLE"]), distinct=True),
                resource_count=Count("subject__resources", filter=Q(subject__resources__is_published=True), distinct=True),
            )
        )
        teacher_names: dict[int, list[str]] = {}
        for offering in offerings:
            teacher_names.setdefault(offering.subject_id, []).append(
                offering.teacher.full_name if offering.teacher else "Teacher to be assigned"
            )

        from academics.serializers import SubjectOfferingSerializer

        context = {"request": request, "teacher_names": teacher_names}
        return Response(
            {
                "count": offerings.count(),
                "results": SubjectOfferingSerializer(offerings, many=True, context=context).data,
            }
        )


class CatalogueView(APIView):
    """Reference data for the rep/admin pickers."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from academics.models import Campus, Program

        return Response(
            {
                "campuses": Campus.objects.filter(is_active=True),
                "programs": Program.objects.filter(is_active=True),
                "academic_years": AcademicYear.objects.filter(is_current=True),
            }
        )


class TimetableView(APIView):
    """
    The student's authoritative timetable.

    Only ``PUBLISHED`` timetables are ever returned, so a pending submission by
    a class representative can never leak into the student view.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        timetable = _published_timetable(scope)
        if timetable is None:
            return Response(
                {
                    "timetable": None,
                    "class": ClassRoomSerializer(scope.profile.class_room).data,
                    "meta": {
                        "message": "Your class timetable has not been published yet.",
                    },
                }
            )
        return Response(
            {
                "timetable": TimetableSerializer(timetable, context={"request": request}).data,
                "class": ClassRoomSerializer(timetable.class_room).data,
                "server_time": timezone.localtime().isoformat(),
            }
        )


class TimetableTodayView(APIView):
    """Today's periods plus the next upcoming class, used by the dashboard."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        now = timezone.localtime()
        weekday = now.weekday()
        timetable = _published_timetable(scope)
        if timetable is None:
            return Response(
                {
                    "has_timetable": False,
                    "date": now.date().isoformat(),
                    "weekday": weekday,
                    "today": [],
                    "next_class": None,
                    "message": "Your class timetable has not been published yet.",
                }
            )

        today_entries = [e for e in timetable.entries.all() if e.day_of_week == weekday]
        next_entry = next(
            (
                e
                for e in timetable.entries.all()
                if e.day_of_week > weekday
                or (e.day_of_week == weekday and e.end_time > now.time())
            ),
            None,
        )
        serialize = lambda entries: [  # noqa: E731 - local shorthand
            {
                "id": e.id,
                "day": e.day_of_week,
                "start": e.start_time.isoformat(),
                "end": e.end_time.isoformat(),
                "subject_code": e.subject.code,
                "subject": e.subject.name,
                "subject_color": e.subject.color_token,
                "teacher": e.teacher.full_name if e.teacher else "",
                "room": e.room,
                "campus": e.campus.name if e.campus else "",
                "note": e.note,
                "is_current": e.start_time <= now.time() < e.end_time,
                "is_past": e.end_time <= now.time(),
            }
            for e in entries
        ]
        return Response(
            {
                "has_timetable": True,
                "date": now.date().isoformat(),
                "weekday": weekday,
                "timetable_version": timetable.version,
                "timetable_published_at": timetable.published_at,
                "today": serialize(today_entries),
                "next_class": (
                    {
                        **serialize([next_entry])[0],
                        "day_label": _day_label(next_entry.day_of_week),
                        "starts_in_minutes": max(
                            0,
                            int(
                                (
                                    timezone.make_aware(
                                        timezone.datetime.combine(
                                            now.date() + timedelta(days=(next_entry.day_of_week - weekday) % 7),
                                            next_entry.start_time,
                                        )
                                    )
                                    - now
                                ).total_seconds()
                            )
                            // 60,
                        ),
                    }
                    if next_entry
                    else None
                ),
            }
        )


def _day_label(value: int) -> str:
    from academics.models import Weekday

    return Weekday.label_for(value)


class TimetableVersionView(APIView):
    """Published and archived versions, with their provenance."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        qs = (
            Timetable.objects.filter(
                class_room_id=scope.class_id,
                section_id=scope.section_id,
                academic_year_id=scope.academic_year_id,
                status__in=[TimetableStatus.PUBLISHED, TimetableStatus.ARCHIVED],
            )
            .select_related("class_room", "section", "approved_by", "created_by")
            .prefetch_related(Prefetch("entries", queryset=_entries_queryset()))
        )
        return Response(
            {
                "count": qs.count(),
                "results": TimetableSerializer(qs, many=True, context={"request": request}).data,
            }
        )


# ---------------------------------------------------------------------------
# Timetable manager workflow
# ---------------------------------------------------------------------------


class TimetableSubmissionListCreateView(APIView):
    """
    GET  — a representative sees their own submissions; staff see the queue.
    POST — submit a timetable (representative or TEL staff only).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if request.user.role in {Role.ADMIN, Role.TEACHER} or request.user.is_superuser:
            qs = TimetableSubmission.objects.select_related(
                "class_room", "section", "submitted_by", "reviewed_by"
            )
            state = request.query_params.get("status")
            if state:
                qs = qs.filter(status__in=state.split(","))
            if request.query_params.get("class"):
                qs = qs.filter(class_room_id=request.query_params["class"])
        else:
            scope = resolve_student_scope(request.user, required=False)
            if scope is None:
                return Response({"count": 0, "results": []})
            if not services.can_manage_class_timetable(
                request.user, scope.class_id, scope.section_id
            ):
                return Response(
                    {
                        "count": 0,
                        "results": [],
                        "message": "You are not the timetable manager for your class.",
                    }
                )
            qs = TimetableSubmission.objects.filter(
                submitted_by=request.user
            ).select_related("class_room", "section", "reviewed_by")

        state = request.query_params.get("status")
        if state:
            qs = qs.filter(status__in=state.split(","))

        try:
            limit = min(int(request.query_params.get("limit", 25)), 100)
        except (TypeError, ValueError):
            limit = 25
        return Response(
            {
                "count": qs.count(),
                "results": TimetableSubmissionSerializer(
                    qs[:limit], many=True, context={"request": request}
                ).data,
            }
        )

    def post(self, request):
        serializer = TimetableSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        class_room = ClassRoom.objects.filter(pk=data["class_id"]).first()
        if class_room is None:
            raise NotFound("That class does not exist.")
        section = Section.objects.filter(pk=data["section_id"], class_room=class_room).first()
        if section is None:
            raise NotFound("That section does not exist in the selected class.")
        academic_year = AcademicYear.objects.filter(pk=class_room.academic_year_id).first()
        if academic_year is None:
            raise TelAPIException("No academic year is configured for this class.")

        image = None
        pdf = None
        if data.get("image"):
            validated = validate_upload(data["image"], field="image")
            image = validated.storage_name
            UploadRecord.objects.create(
                uploader=request.user,
                purpose=UploadRecord.Purpose.TIMETABLE_IMAGE,
                storage_path=validated.storage_name,
                original_name=validated.original_name,
                content_type=validated.content_type,
                size=validated.size,
                checksum=validated.checksum,
                visibility=UploadRecord.Visibility.STAFF,
                class_room=class_room,
                section=section,
            )
        if data.get("pdf"):
            validated = validate_upload(data["pdf"], field="pdf")
            pdf = validated.storage_name
            UploadRecord.objects.create(
                uploader=request.user,
                purpose=UploadRecord.Purpose.TIMETABLE_PDF,
                storage_path=validated.storage_name,
                original_name=validated.original_name,
                content_type=validated.content_type,
                size=validated.size,
                checksum=validated.checksum,
                visibility=UploadRecord.Visibility.STAFF,
                class_room=class_room,
                section=section,
            )

        submission = services.create_submission(
            user=request.user,
            class_room=class_room,
            section=section,
            academic_year=academic_year,
            summary=data.get("summary", ""),
            change_note=data.get("change_note", ""),
            payload=data.get("entries"),
            image=image,
            pdf=pdf,
        )
        return Response(
            TimetableSubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class TimetableSubmissionReviewView(APIView):
    """Reviewer actions: start review, approve, reject, request changes."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        if request.user.role not in {Role.ADMIN, Role.TEACHER} and not request.user.is_superuser:
            raise Forbidden("Only TEL staff can review timetable submissions.")
        submission = TimetableSubmission.objects.filter(pk=pk).select_related(
            "class_room", "section", "submitted_by"
        ).first()
        if submission is None:
            raise NotFound("That submission no longer exists.")

        decision = (request.data.get("decision") or "").strip().upper()
        if decision not in services.REVIEW_TRANSITIONS:
            raise TelAPIException(
                "Choose one of: " + ", ".join(sorted(services.REVIEW_TRANSITIONS.keys()))
            )
        note = (request.data.get("note") or "").strip()
        if decision in {TimetableStatus.REJECTED, TimetableStatus.CHANGES_REQUESTED} and not note:
            raise TelAPIException("Explain what needs to change so the student can act on it.")

        services.review_submission(
            submission=submission, reviewer=request.user, decision=decision, note=note
        )
        return Response(
            TimetableSubmissionSerializer(submission, context={"request": request}).data
        )


class TimetableSubmissionPublishView(APIView):
    """
    Publishes a reviewed submission as a new timetable version.

    Requires both an approved submission *and* a separate publish call so an
    approval can never silently go live.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        if request.user.role != Role.ADMIN and not request.user.is_superuser:
            raise Forbidden("Only a TEL administrator can publish a timetable.")
        submission = TimetableSubmission.objects.filter(pk=pk).select_related(
            "class_room", "section", "academic_year"
        ).first()
        if submission is None:
            raise NotFound("That submission no longer exists.")
        if submission.status != TimetableStatus.APPROVED:
            raise TelAPIException(
                "Approve the submission before publishing it to the class."
            )

        timetable = services.materialise_timetable_from_submission(
            submission=submission,
            publisher=request.user,
            change_note=(request.data.get("change_note") or "").strip(),
        )
        services.publish_timetable(
            timetable=timetable,
            publisher=request.user,
            effective_from=request.data.get("effective_from") or None,
            change_note=(request.data.get("change_note") or "").strip(),
        )
        return Response(TimetableSerializer(timetable, context={"request": request}).data)


class ClassRepresentativeView(APIView):
    """Admin: see and assign class representatives."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != Role.ADMIN and not request.user.is_superuser:
            raise Forbidden("Only a TEL administrator can manage representatives.")
        qs = ClassRepresentative.objects.select_related(
            "class_room", "section", "user", "assigned_by"
        )
        if request.query_params.get("class"):
            qs = qs.filter(class_room_id=request.query_params["class"])
        if request.query_params.get("active", "true") == "true":
            qs = qs.filter(is_active=True)
        return Response(
            {
                "count": qs.count(),
                "results": ClassRepresentativeSerializer(qs, many=True).data,
            }
        )

    def post(self, request):
        from django.db import transaction

        if request.user.role != Role.ADMIN and not request.user.is_superuser:
            raise Forbidden("Only a TEL administrator can assign representatives.")

        from academics.models import ClassRoom

        class_id = request.data.get("class_id")
        section_id = request.data.get("section_id")
        user_id = request.data.get("user_id")

        class_room = ClassRoom.objects.filter(pk=class_id).first()
        section = Section.objects.filter(pk=section_id, class_room=class_room).first() if class_room else None
        student = User.objects.filter(pk=user_id, role=Role.STUDENT).first()
        if class_room is None or section is None:
            raise TelAPIException("Choose a valid class and section.")
        if student is None:
            raise TelAPIException("Choose a valid student.")

        profile = getattr(student, "student_profile", None)
        if profile is None or profile.class_room_id != class_room.pk or profile.section_id != section.pk:
            raise TelAPIException(
                "The representative must be a student of the selected class section."
            )

        with transaction.atomic():
            ClassRepresentative.objects.filter(
                class_room=class_room, section=section, is_active=True
            ).update(is_active=False, ends_on=timezone.localdate())
            record, created = ClassRepresentative.objects.update_or_create(
                class_room=class_room,
                section=section,
                user=student,
                defaults={
                    "assigned_by": request.user,
                    "is_active": True,
                    "ends_on": None,
                },
            )
            if student.role == Role.STUDENT:
                student.role = Role.CLASS_REPRESENTATIVE
                student.save(update_fields=["role"])

        log_event(
            request,
            action="class_representative.assigned",
            user=request.user,
            entity=record,
            summary=f"{student.full_name} assigned to {section}",
            metadata={"class_id": class_room.pk, "section_id": section.pk, "student_id": student.pk},
        )
        return Response(
            ClassRepresentativeSerializer(record).data, status=status.HTTP_201_CREATED
        )


class SubjectCatalogueView(APIView):
    """All subjects in TEL, for staff tooling and filter lists."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q as _Q

        from academics.models import Subject

        qs = Subject.objects.filter(is_active=True).select_related("program")
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(_Q(name__icontains=search) | _Q(code__icontains=search))
        if request.query_params.get("program"):
            qs = qs.filter(program_id=request.query_params["program"])
        return Response({"count": qs.count(), "results": SubjectSerializer(qs, many=True).data})
