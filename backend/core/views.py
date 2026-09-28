from __future__ import annotations

from django.db.models import Q
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from academics.models import ClassRoom
from common.exceptions import TelAPIException, Forbidden
from common.pagination import TelPagination
from core.audit import log_event
from core.models import AuditLog, Notification, NotificationState, UploadRecord
from core.serializers import AuditLogSerializer, MarkReadSerializer, NotificationSerializer


def _can_access(user, record: UploadRecord) -> bool:
    if not record.is_active:
        return False
    if user.is_superuser or user.role in {Role.ADMIN, Role.TEACHER}:
        return True
    if record.uploader_id == user.pk:
        return True
    if user.pk in (record.allowed_user_ids or []):
        return True
    if record.visibility == UploadRecord.Visibility.OWNER:
        return False
    if record.visibility == UploadRecord.Visibility.CLASS:
        profile = getattr(user, "student_profile", None)
        if not profile or not record.class_room_id:
            return False
        if profile.class_room_id != record.class_room_id:
            return False
        if record.section_id and profile.section_id != record.section_id:
            return False
        return True
    return False


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.visible_to(request.user)
        state = request.query_params.get("state")
        if state == "unread":
            qs = qs.unread()
        elif state == "read":
            qs = qs.filter(state=NotificationState.READ)
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        try:
            limit = min(int(request.query_params.get("limit", 30)), 100)
        except (TypeError, ValueError):
            limit = 30
        qs = qs[:limit]
        unread_count = Notification.objects.visible_to(request.user).unread().count()
        return Response(
            {
                "results": NotificationSerializer(qs, many=True).data,
                "unread_count": unread_count,
            }
        )

    def post(self, request):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("ids") or []
        mark_all = serializer.validated_data.get("all", False)
        qs = Notification.objects.visible_to(request.user)
        if mark_all:
            qs = qs.unread()
        elif ids:
            qs = qs.filter(id__in=ids)
        else:
            raise TelAPIException("Nothing selected to mark as read.")
        from django.utils import timezone

        # Collect the ids *before* the update: afterwards the ``unread()`` filter
        # would no longer match the rows that were just marked.
        to_mark = list(qs.values_list("pk", flat=True))
        updated = qs.update(state=NotificationState.READ)
        if to_mark:
            Notification.objects.filter(pk__in=to_mark).update(read_at=timezone.now())
        return Response({"marked": updated})


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"unread_count": Notification.objects.visible_to(request.user).unread().count()}
        )


class FileAccessView(APIView):
    """
    Streams a stored file after an authorisation check.

    Uploads are stored under non-guessable keys; this view is the only way to
    read them and it verifies the caller's entitlement first.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        record = UploadRecord.objects.filter(pk=pk, is_active=True).first()
        if record is None:
            raise Http404
        if not _can_access(request.user, record):
            log_event(
                request,
                action="file.access_denied",
                entity=record,
                metadata={"purpose": record.purpose},
            )
            raise Forbidden("You do not have access to this file.")

        from django.core.files.storage import default_storage

        if not default_storage.exists(record.storage_path):
            raise Http404
        handle = default_storage.open(record.storage_path, "rb")
        response = FileResponse(handle, content_type=record.content_type)
        response["Content-Disposition"] = f'inline; filename="{record.original_name}"'
        response["Content-Length"] = str(record.size)
        response["Cache-Control"] = "private, max-age=300"
        response["X-Content-Type-Options"] = "nosniff"
        log_event(request, action="file.accessed", entity=record)
        return response


class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {Role.ADMIN, Role.TEACHER} and not request.user.is_superuser:
            raise Forbidden("You do not have permission to view the audit log.")
        qs = AuditLog.objects.select_related("actor")
        params = request.query_params
        action = params.get("action")
        if action:
            qs = qs.filter(action__startswith=action)
        entity_type = params.get("entity_type")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        role = params.get("role")
        if role:
            qs = qs.filter(actor_role=role)
        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(action__icontains=search)
                | Q(summary__icontains=search)
                | Q(actor__full_name__icontains=search)
            )
        paginator = TelPagination()
        page = paginator.paginate_queryset(qs.order_by("-created_at"), request, view=self)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)


class LookupDataView(APIView):
    """Filter option lists — campuses, programmes, classes, subjects, years."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from academics.models import AcademicYear, Campus, ClassRoom, Program, Section, Subject

        campus_id = request.query_params.get("campus")
        program_id = request.query_params.get("program")
        class_id = request.query_params.get("class")

        classes = ClassRoom.objects.filter(is_active=True).select_related(
            "program", "campus", "academic_year"
        )
        if campus_id:
            classes = classes.filter(campus_id=campus_id)
        if program_id:
            classes = classes.filter(program_id=program_id)

        sections = Section.objects.filter(is_active=True).select_related("class_room")
        if class_id:
            sections = sections.filter(class_room_id=class_id)
        elif classes.exists():
            sections = sections.filter(class_room__in=classes)

        return Response(
            {
                "campuses": [
                    {"id": c.id, "code": c.code, "name": c.name}
                    for c in Campus.objects.filter(is_active=True)
                ],
                "programs": [
                    {"id": p.id, "code": p.code, "name": p.name, "level": p.level}
                    for p in Program.objects.filter(is_active=True)
                ],
                "classes": [
                    {
                        "id": c.id,
                        "code": c.code,
                        "name": c.name,
                        "display_name": c.display_name,
                        "campus_id": c.campus_id,
                        "program_id": c.program_id,
                        "academic_year_id": c.academic_year_id,
                        "section_count": c.sections.filter(is_active=True).count(),
                    }
                    for c in classes
                ],
                "sections": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "class_id": s.class_room_id,
                        "display_name": s.display_name,
                        "student_count": s.students.count(),
                    }
                    for s in sections
                ],
                "subjects": [
                    {"id": s.id, "code": s.code, "name": s.name, "program_id": s.program_id}
                    for s in Subject.objects.filter(is_active=True)
                ],
                "academic_years": [
                    {
                        "id": y.id,
                        "code": y.code,
                        "label": y.label,
                        "is_current": y.is_current,
                        "class_count": ClassRoom.objects.filter(
                            academic_year=y, is_active=True
                        ).count(),
                    }
                    for y in AcademicYear.objects.all()
                ],
            }
        )


class ClassToolkitView(APIView):
    """Data a class representative needs: their classes and offered subjects."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from academics.models import ClassRepresentative
        from accounts.permissions import has_capability

        if not has_capability(request.user, "submit_timetable"):
            return Response({"assignments": [], "subjects": []})

        assignments = (
            ClassRepresentative.objects.filter(user=request.user, is_active=True)
            .select_related("class_room", "section", "class_room__program", "class_room__campus")
        )
        payload = []
        for assignment in assignments:
            subjects = list(
                assignment.class_room.offerings.filter(is_active=True)
                .select_related("subject", "teacher")
                .values("subject__id", "subject__code", "subject__name", "teacher__full_name")
            )
            payload.append(
                {
                    "class_id": assignment.class_room_id,
                    "section_id": assignment.section_id,
                    "class_name": assignment.class_room.display_name,
                    "section_name": assignment.section.name,
                    "assigned_at": assignment.created_at,
                    "ends_on": assignment.ends_on,
                    "subjects": subjects,
                }
            )
        return Response({"assignments": payload})
