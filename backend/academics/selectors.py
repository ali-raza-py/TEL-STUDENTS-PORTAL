"""
Read-side helpers shared across the API.

Two ideas live here:

1. **Brief projections** — small cached dicts used by dropdown filters so the
   frontend never has to hardcode campus/class/subject options.
2. **Scope resolution** — every student-facing query is narrowed to the
   authenticated student's own profile, so a caller cannot widen their view by
   editing a query parameter.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Q, QuerySet

from accounts.models import Role, StudentProfile
from academics.models import AcademicYear, Campus, ClassRoom, Program, Section, Subject
from common.exceptions import TelAPIException


def _cached(key: str, builder):
    value = cache.get(key)
    if value is None:
        value = builder()
        cache.set(key, value, 600)
    return value


def campus_brief() -> list[dict]:
    def build():
        return [
            {"id": c.id, "code": c.code, "name": c.name}
            for c in Campus.objects.filter(is_active=True)
        ]

    return _cached("brief:campus", build)


def program_brief() -> list[dict]:
    def build():
        return [
            {"id": p.id, "code": p.code, "name": p.name, "level": p.level}
            for p in Program.objects.filter(is_active=True)
        ]

    return _cached("brief:program", build)


def class_brief(campus_id: int | None = None, program_id: int | None = None) -> list[dict]:
    def build():
        qs = ClassRoom.objects.filter(is_active=True).select_related("program", "campus", "academic_year")
        if campus_id:
            qs = qs.filter(campus_id=campus_id)
        if program_id:
            qs = qs.filter(program_id=program_id)
        return [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "display_name": c.display_name,
                "campus_id": c.campus_id,
                "program_id": c.program_id,
                "academic_year_id": c.academic_year_id,
            }
            for c in qs
        ]

    return _cached(f"brief:class:{campus_id}:{program_id}", build)


def section_brief(class_id: int | None = None) -> list[dict]:
    def build():
        qs = Section.objects.filter(is_active=True).select_related("class_room")
        if class_id:
            qs = qs.filter(class_room_id=class_id)
        return [
            {
                "id": s.id,
                "name": s.name,
                "class_id": s.class_room_id,
                "display_name": s.display_name,
            }
            for s in qs
        ]

    return _cached(f"brief:section:{class_id}", build)


def subject_brief() -> list[dict]:
    def build():
        return [
            {"id": s.id, "code": s.code, "name": s.name, "program_id": s.program_id}
            for s in Subject.objects.filter(is_active=True)
        ]

    return _cached("brief:subject", build)


def academic_year_brief() -> list[dict]:
    def build():
        return [
            {"id": y.id, "code": y.code, "label": y.label, "is_current": y.is_current}
            for y in AcademicYear.objects.all()
        ]

    return _cached("brief:year", build)


def invalidate_briefs() -> None:
    """Drops the cached filter option lists after a catalogue change."""
    for key in ("brief:campus", "brief:program", "brief:subject", "brief:year"):
        cache.delete(key)
    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern("brief:class:*")
        cache.delete_pattern("brief:section:*")


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class StudentScope:
    """Resolved, immutable academic placement for the current student."""

    __slots__ = (
        "profile",
        "student_id",
        "user_id",
        "campus_id",
        "program_id",
        "class_id",
        "section_id",
        "academic_year_id",
    )

    def __init__(self, profile: StudentProfile):
        self.profile = profile
        self.student_id = profile.pk
        self.user_id = profile.user_id
        self.campus_id = profile.campus_id
        self.program_id = profile.program_id
        self.class_id = profile.class_room_id
        self.section_id = profile.section_id
        self.academic_year_id = profile.academic_year_id

    @property
    def is_complete(self) -> bool:
        return bool(self.class_id and self.section_id and self.academic_year_id)

    def require(self) -> "StudentScope":
        if not self.is_complete:
            raise TelAPIException(
                "Your class placement is incomplete. Please contact your TEL class teacher.",
                code="profile_incomplete",
            )
        return self


def resolve_student_scope(user, *, required: bool = True) -> StudentScope | None:
    if user is None or not user.is_authenticated or user.role not in {
        Role.STUDENT,
        Role.CLASS_REPRESENTATIVE,
    }:
        return None
    profile = getattr(user, "student_profile", None)
    if profile is None:
        if required:
            raise TelAPIException(
                "This account is not linked to a student record.",
                code="profile_missing",
            )
        return None
    scope = StudentScope(profile)
    return scope.require() if required else scope


def scope_class_q(scope: StudentScope) -> Q:
    """Restricts a queryset to records intended for the student's own class."""
    return Q(class_room_id=scope.class_id) & Q(
        Q(section_id=scope.section_id) | Q(section__isnull=True)
    )


def scope_year_q(scope: StudentScope) -> Q:
    return Q(academic_year_id=scope.academic_year_id)


def is_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.role in {Role.ADMIN, Role.TEACHER} or user.is_superuser))


def staff_scope_filter(user, queryset: QuerySet) -> QuerySet:
    """Teachers see their own campus; admins see everything."""
    if user.is_superuser or user.role == Role.ADMIN:
        return queryset
    profile = getattr(user, "teacher_profile", None)
    if profile and profile.campus_id:
        return queryset.filter(campus_id=profile.campus_id)
    return queryset
