from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.selectors import resolve_student_scope
from accounts.models import Role
from common.exceptions import TelAPIException, Forbidden
from common.pagination import TelPagination
from common.uploads import validate_upload
from engagement import selectors
from engagement.models import (
    AcademicEvent,
    Announcement,
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    AttendanceRecord,
    Feedback,
    RequestStatus,
    Resource,
    StudentRequest,
)
from engagement.serializers import (
    AcademicEventSerializer,
    AnnouncementSerializer,
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    AttendanceRecordSerializer,
    FeedbackCreateSerializer,
    FeedbackSerializer,
    ResourceSerializer,
    StudentRequestCreateSerializer,
    StudentRequestSerializer,
)
from core.audit import log_event
from core.models import UploadRecord
from core.notifications import notify, notify_class


def _is_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.role in {Role.ADMIN, Role.TEACHER} or user.is_superuser))


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


class StudentAttendanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        summary = selectors.attendance_summary(scope.profile)
        from django.conf import settings

        summary["target_percentage"] = settings.TEL_ATTENDANCE_TARGET
        summary["meets_target"] = (
            summary["overall_percentage"] is not None
            and summary["overall_percentage"] >= settings.TEL_ATTENDANCE_TARGET
        )
        return Response(summary)


class StudentAttendanceRecordsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        qs = AttendanceRecord.objects.filter(student=scope.profile).select_related("subject")
        params = request.query_params
        if params.get("subject"):
            qs = qs.filter(subject_id=params["subject"])
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        if params.get("from"):
            qs = qs.filter(date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(date__lte=params["to"])

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by("-date", "subject__code"), request, view=self)
        return paginator.get_paginated_response(AttendanceRecordSerializer(page, many=True).data)


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


class StudentAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user)
        qs = (
            Assignment.objects.filter(
                is_published=True, class_room_id=scope.class_id
            )
            .filter(Q(section_id=scope.section_id) | Q(section__isnull=True))
            .select_related("subject", "teacher", "class_room")
            .prefetch_related("submissions")
        )
        params = request.query_params
        if params.get("subject"):
            qs = qs.filter(subject_id=params["subject"])
        if params.get("from"):
            qs = qs.filter(due_on__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(due_on__lte=params["to"])

        ordering = "due_on" if params.get("ordering") == "due_on" else "-due_on"
        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by(ordering), request, view=self)
        context = {"request": request, "student_id": scope.student_id}
        return paginator.get_paginated_response(
            AssignmentSerializer(page, many=True, context=context).data
        )


class AssignmentSubmissionCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, pk: int):
        scope = resolve_student_scope(request.user)
        assignment = Assignment.objects.filter(
            pk=pk, is_published=True, class_room_id=scope.class_id
        ).first()
        if assignment is None:
            raise NotFound("That assignment could not be found.")
        if assignment.section_id and assignment.section_id != scope.section_id:
            raise NotFound("That assignment could not be found.")

        upload = request.FILES.get("file")
        notes = (request.data.get("notes") or "").strip()
        if not upload and not notes:
            raise TelAPIException("Attach a file or add a note before submitting.")

        storage_name = None
        if upload:
            validated = validate_upload(upload, field="file")
            storage_name = validated.storage_name
            UploadRecord.objects.create(
                uploader=request.user,
                purpose=UploadRecord.Purpose.SUBMISSION,
                storage_path=validated.storage_name,
                original_name=validated.original_name,
                content_type=validated.content_type,
                size=validated.size,
                checksum=validated.checksum,
                visibility=UploadRecord.Visibility.STAFF,
                class_room=assignment.class_room,
                section=assignment.section,
                allowed_user_ids=[request.user.pk],
            )

        submission, created = AssignmentSubmission.objects.update_or_create(
            assignment=assignment,
            student=scope.profile,
            defaults={
                "file": storage_name,
                "notes": notes,
                "submitted_at": timezone.now(),
                "status": (
                    AssignmentStatus.LATE
                    if assignment.due_on < timezone.localdate()
                    else AssignmentStatus.SUBMITTED
                ),
            },
        )
        log_event(
            request,
            action="assignment.submitted",
            user=request.user,
            entity=submission,
            summary=assignment.title,
            metadata={"assignment_id": assignment.pk, "late": submission.status == AssignmentStatus.LATE},
        )
        return Response(
            AssignmentSubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ResourceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Resource.objects.filter(is_published=True).select_related(
            "subject", "class_room", "academic_year"
        )
        if _is_staff(request.user):
            if request.query_params.get("class"):
                qs = qs.filter(class_room_id=request.query_params["class"])
        else:
            scope = resolve_student_scope(request.user)
            qs = qs.filter(Q(class_room_id__isnull=True) | Q(class_room_id=scope.class_id))
            qs = qs.filter(Q(section_id__isnull=True) | Q(section_id=scope.section_id))

        params = request.query_params
        if params.get("category"):
            qs = qs.filter(category__in=params["category"].split(","))
        if params.get("subject"):
            qs = qs.filter(subject_id=params["subject"])
        if params.get("chapter"):
            qs = qs.filter(chapter__icontains=params["chapter"])
        if params.get("year"):
            qs = qs.filter(academic_year_id=params["year"])
        if params.get("class"):
            qs = qs.filter(class_room_id=params["class"])

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(chapter__icontains=search)
            )

        ordering = params.get("ordering") if params.get("ordering") in {
            "-published_at", "published_at", "title", "-created_at"
        } else "-published_at"

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by(ordering), request, view=self)
        return paginator.get_paginated_response(
            ResourceSerializer(page, many=True, context={"request": request}).data
        )


class ResourceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        resource = Resource.objects.filter(pk=pk, is_published=True).select_related(
            "subject", "class_room", "academic_year"
        ).first()
        if resource is None:
            raise NotFound("That resource could not be found.")
        if not _is_staff(request.user):
            scope = resolve_student_scope(request.user)
            if resource.class_room_id and resource.class_room_id != scope.class_id:
                raise NotFound("That resource could not be found.")
        return Response(ResourceSerializer(resource, context={"request": request}).data)


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


class AnnouncementListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _is_staff(request.user):
            return _announcement_staff_list(request)

        scope = resolve_student_scope(request.user, required=False)
        now = timezone.now()
        qs = (
            Announcement.objects.filter(is_published=True, published_at__lte=now)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .select_related("campus", "program", "class_room", "section", "academic_year", "created_by")
            .exclude(audience="STAFF")
        )
        if scope is not None:
            profile = scope.profile
            qs = qs.filter(
                Q(audience="ALL_STUDENTS")
                | Q(audience="CAMPUS", campus_id=profile.campus_id)
                | Q(audience="PROGRAM", program_id=profile.program_id)
                | Q(audience="CLASS", class_room_id=profile.class_room_id)
                | Q(audience="SECTION", section_id=profile.section_id)
                | Q(audience="ACADEMIC_YEAR", academic_year_id=profile.academic_year_id)
            )

        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
        if request.query_params.get("audience"):
            qs = qs.filter(audience=request.query_params["audience"])

        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by("-is_pinned", "-published_at"), request, view=self)
        return paginator.get_paginated_response(
            AnnouncementSerializer(page, many=True, context={"request": request}).data
        )


def _announcement_staff_list(request):
    qs = Announcement.objects.select_related(
        "campus", "program", "class_room", "section", "academic_year", "created_by"
    )
    if request.query_params.get("status"):
        qs = qs.filter(is_published=request.query_params["status"] == "published")
    try:
        limit = min(int(request.query_params.get("limit", 25)), 100)
    except (TypeError, ValueError):
        limit = 25
    return Response(
        {
            "count": qs.count(),
            "results": AnnouncementSerializer(
                qs[:limit], many=True, context={"request": request}
            ).data,
        }
    )


class AnnouncementManageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can publish announcements.")
        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        audience = (request.data.get("audience") or "ALL_STUDENTS").upper()
        if not title or not body:
            raise TelAPIException("An announcement needs a title and a body.")
        if audience not in dict(Announcement._meta.get_field("audience").choices):
            raise TelAPIException("Choose a valid audience.")

        attachment_name = ""
        upload = request.FILES.get("attachment")
        if upload:
            validated = validate_upload(upload, field="attachment")
            attachment_name = validated.storage_name

        announcement = Announcement.objects.create(
            title=title[:200],
            body=body,
            audience=audience,
            campus_id=request.data.get("campus") or None,
            program_id=request.data.get("program") or None,
            class_room_id=request.data.get("class_room") or None,
            section_id=request.data.get("section") or None,
            academic_year_id=request.data.get("academic_year") or None,
            attachment=attachment_name or None,
            is_pinned=bool(request.data.get("is_pinned")),
            is_published=True,
            published_at=timezone.now(),
            created_by=request.user,
        )
        from core.notifications import students_for_audience

        for student in students_for_audience(
            campus_id=announcement.campus_id,
            program_id=announcement.program_id,
            class_id=announcement.class_room_id,
            section_id=announcement.section_id,
            academic_year_id=announcement.academic_year_id,
        ):
            if announcement.audience == "ALL_STUDENTS" or announcement.targets(
                getattr(student, "student_profile", None)
            ):
                notify(
                    student,
                    category="ANNOUNCEMENT",
                    title=announcement.title,
                    body=announcement.body[:240],
                    action_url="/announcements",
                    action_label="Read announcement",
                    dedupe_key=f"announcement:{announcement.pk}",
                )
        log_event(
            request, action="announcement.published", user=request.user, entity=announcement,
            summary=announcement.title, metadata={"audience": audience},
        )
        return Response(
            AnnouncementSerializer(announcement, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


class AcademicCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.localtime()
        start = _parse_date(request.query_params.get("from"), (now - timedelta(days=7)).date())
        end = _parse_date(request.query_params.get("to"), (now + timedelta(days=60)).date())

        qs = AcademicEvent.objects.filter(starts_at__date__gte=start, starts_at__date__lte=end)
        if not _is_staff(request.user):
            scope = resolve_student_scope(request.user, required=False)
            if scope is not None:
                profile = scope.profile
                qs = qs.filter(
                    Q(campus_id__isnull=True) | Q(campus_id=profile.campus_id)
                ).filter(Q(program_id__isnull=True) | Q(program_id=profile.program_id))
                qs = qs.filter(Q(class_room_id__isnull=True) | Q(class_room_id=profile.class_room_id))
                qs = qs.filter(Q(section_id__isnull=True) | Q(section_id=profile.section_id))
        else:
            if request.query_params.get("campus"):
                qs = qs.filter(campus_id=request.query_params["campus"])

        events = list(qs.select_related("subject", "campus").order_by("starts_at"))
        return Response(
            {
                "range": {"from": start.isoformat(), "to": end.isoformat()},
                "events": AcademicEventSerializer(events, many=True).data,
            }
        )


def _parse_date(raw, fallback):
    if not raw:
        return fallback
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return fallback


class AcademicEventManageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can add calendar events.")
        title = (request.data.get("title") or "").strip()
        starts_at = parse_datetime(request.data.get("starts_at") or "")
        if not title or not starts_at:
            raise TelAPIException("A calendar event needs a title and a start time.")
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        ends_at = parse_datetime(request.data.get("ends_at") or "") if request.data.get("ends_at") else None

        event = AcademicEvent.objects.create(
            title=title[:200],
            description=(request.data.get("description") or "").strip(),
            event_type=(request.data.get("event_type") or "TEL_EVENT").upper(),
            starts_at=starts_at,
            ends_at=ends_at,
            is_all_day=bool(request.data.get("is_all_day")),
            campus_id=request.data.get("campus") or None,
            program_id=request.data.get("program") or None,
            class_room_id=request.data.get("class_room") or None,
            section_id=request.data.get("section") or None,
            subject_id=request.data.get("subject") or None,
            created_by=request.user,
        )
        log_event(request, action="event.created", user=request.user, entity=event, summary=event.title)
        return Response(
            AcademicEventSerializer(event).data, status=status.HTTP_201_CREATED
        )


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class StudentRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if _is_staff(request.user):
            return _request_queue(request)

        scope = resolve_student_scope(request.user)
        qs = StudentRequest.objects.filter(student=scope.profile)
        if request.query_params.get("status"):
            qs = qs.filter(status__in=request.query_params["status"].split(","))
        paginator = TelPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            StudentRequestSerializer(page, many=True, context={"request": request}).data
        )

    def post(self, request):
        scope = resolve_student_scope(request.user)
        serializer = StudentRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        upload = request.FILES.get("attachment")
        attachment_name = ""
        if upload:
            validated = validate_upload(upload, field="attachment")
            attachment_name = validated.storage_name

        ticket = StudentRequest.objects.create(
            student=scope.profile,
            request_type=data["request_type"],
            subject_line=data["subject_line"],
            description=data["description"],
            related_date=data.get("related_date"),
            attachment=attachment_name or None,
            status=RequestStatus.PENDING,
        )
        if attachment_name:
            UploadRecord.objects.create(
                uploader=request.user,
                purpose=UploadRecord.Purpose.REQUEST,
                storage_path=attachment_name,
                original_name=upload.name[:180],
                content_type=getattr(upload, "content_type", "") or "application/octet-stream",
                size=upload.size,
                checksum="",
                visibility=UploadRecord.Visibility.OWNER,
                allowed_user_ids=[request.user.pk],
            )

        log_event(
            request, action="request.created", user=request.user, entity=ticket,
            summary=f"{ticket.ticket_id} · {ticket.subject_line}",
            metadata={"type": ticket.request_type},
        )
        return Response(
            StudentRequestSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def _request_queue(request):
    from engagement.serializers import ReferenceListsView  # noqa: F401  (documented choice sets)

    qs = StudentRequest.objects.select_related("student", "student__user", "responded_by")
    params = request.query_params
    if params.get("status"):
        qs = qs.filter(status__in=params["status"].split(","))
    if params.get("type"):
        qs = qs.filter(request_type=params["type"])
    if params.get("class"):
        qs = qs.filter(student__class_room_id=params["class"])
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(ticket_id__icontains=search)
            | Q(subject_line__icontains=search)
            | Q(student__user__full_name__icontains=search)
        )
    try:
        limit = min(int(params.get("limit", 50)), 200)
    except (TypeError, ValueError):
        limit = 50
    return Response(
        {
            "count": qs.count(),
            "open_count": qs.filter(
                status__in=[RequestStatus.PENDING, RequestStatus.IN_REVIEW]
            ).count(),
            "results": StudentRequestSerializer(
                qs[:limit], many=True, context={"request": request}
            ).data,
        }
    )


class StaffRequestUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        if not _is_staff(request.user):
            raise Forbidden("Only TEL staff can respond to requests.")
        ticket = StudentRequest.objects.filter(pk=pk).select_related("student__user").first()
        if ticket is None:
            raise NotFound("That ticket could not be found.")

        new_status = (request.data.get("status") or "").upper()
        if new_status not in dict(RequestStatus._meta.get_field("status").choices):
            raise TelAPIException("Choose a valid ticket status.")
        response_text = (request.data.get("response") or "").strip()
        if new_status in {RequestStatus.RESOLVED, RequestStatus.REJECTED} and not response_text:
            raise TelAPIException("Write a response so the student knows the outcome.")

        ticket.status = new_status
        ticket.admin_response = response_text
        if new_status in {RequestStatus.RESOLVED, RequestStatus.REJECTED, RequestStatus.CLOSED}:
            ticket.responded_by = request.user
            ticket.responded_at = timezone.now()
        ticket.save()

        notify(
            ticket.student.user,
            category="REQUEST",
            title=f"Request {ticket.ticket_id} — {ticket.get_status_display()}",
            body=response_text or f"Your request is now {ticket.get_status_display().lower()}.",
            action_url="/requests",
            action_label="View request",
            dedupe_key=f"request-update:{ticket.pk}:{new_status}",
        )
        log_event(
            request, action="request.updated", user=request.user, entity=ticket,
            summary=f"{ticket.ticket_id} → {new_status}",
        )
        return Response(StudentRequestSerializer(ticket, context={"request": request}).data)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class StudentFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _is_staff(request.user):
            return _feedback_inbox(request)
        scope = resolve_student_scope(request.user)
        qs = Feedback.objects.filter(student=scope.profile)
        return Response(
            {
                "count": qs.count(),
                "results": FeedbackSerializer(qs[:20], many=True).data,
            }
        )

    def post(self, request):
        scope = resolve_student_scope(request.user)
        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        feedback = Feedback.objects.create(
            student=scope.profile,
            category=data["category"],
            rating=data.get("rating"),
            message=data["message"],
        )
        log_event(
            request, action="feedback.submitted", user=request.user, entity=feedback,
            summary=f"{feedback.get_category_display()} · rating {feedback.rating or 'n/a'}",
        )
        return Response(FeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


def _feedback_inbox(request):
    qs = Feedback.objects.select_related("student", "student__user")
    if request.query_params.get("category"):
        qs = qs.filter(category=request.query_params["category"])
    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
    except (TypeError, ValueError):
        limit = 50
    return Response({"count": qs.count(), "results": FeedbackSerializer(qs[:limit], many=True).data})
