"""
Role based access control.

Permissions are expressed once, here, and enforced by the API layer. Hiding a
button in the UI is a convenience only — every view below also checks the
caller's role, and every student-scoped queryset is filtered to the caller's own
profile so that manipulating an identifier in a request cannot expose another
student's records.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role

# Capability catalogue. The frontend reads the same map through /api/auth/me/
# purely to decide what to render — never to decide what is allowed.
CAPABILITIES: dict[str, set[str]] = {
    Role.STUDENT: {
        "view_dashboard",
        "view_timetable",
        "view_subjects",
        "view_papers",
        "practice_papers",
        "view_results",
        "view_attendance",
        "view_assignments",
        "submit_assignments",
        "view_resources",
        "view_announcements",
        "view_notifications",
        "view_calendar",
        "submit_requests",
        "submit_feedback",
        "edit_profile_contact",
        "change_password",
    },
    Role.CLASS_REPRESENTATIVE: {
        "view_dashboard",
        "view_timetable",
        "view_subjects",
        "view_papers",
        "practice_papers",
        "view_results",
        "view_attendance",
        "view_assignments",
        "submit_assignments",
        "view_resources",
        "view_announcements",
        "view_notifications",
        "view_calendar",
        "submit_requests",
        "submit_feedback",
        "edit_profile_contact",
        "change_password",
        "submit_timetable",
        "report_timetable_change",
    },
    Role.TEACHER: {
        "view_dashboard",
        "view_students",
        "review_timetable_submissions",
        "review_requests",
        "manage_announcements",
        "manage_academic_events",
        "view_audit_log",
    },
    Role.ADMIN: {
        "view_dashboard",
        "view_students",
        "review_timetable_submissions",
        "publish_timetable",
        "manage_papers",
        "publish_papers",
        "manage_results",
        "publish_results",
        "manage_attendance",
        "manage_assignments",
        "manage_resources",
        "manage_announcements",
        "manage_academic_events",
        "assign_class_representatives",
        "review_requests",
        "review_feedback",
        "manage_students",
        "view_audit_log",
    },
}


def capabilities_for(role: str) -> list[str]:
    return sorted(CAPABILITIES.get(role, set()))


def has_capability(user, capability: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return capability in CAPABILITIES.get(user.role, set())


class HasCapability(BasePermission):
    message = "You do not have permission to perform this action."

    def __init__(self, *capabilities: str, require_all: bool = False):
        self.capabilities = capabilities
        self.require_all = require_all
        super().__init__()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not self.capabilities:
            return True
        if self.require_all:
            return all(has_capability(user, c) for c in self.capabilities)
        return any(has_capability(user, c) for c in self.capabilities)


class IsRole(BasePermission):
    """Allow only the listed roles. Admins always pass."""

    message = "This area is not available for your role."

    def __init__(self, *roles: str):
        self.roles = roles
        super().__init__()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.role == Role.ADMIN:
            return True
        return user.role in self.roles


class IsAdminOrTeacher(IsRole):
    def __init__(self):
        super().__init__(Role.ADMIN, Role.TEACHER)


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


class IsOwnerOrStaff(BasePermission):
    """Object level check: the owner of the record, or a member of TEL staff."""

    message = "You may only access your own records."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user.is_superuser or user.role in {Role.ADMIN, Role.TEACHER}:
            return True
        owner = getattr(obj, "student", None) or getattr(obj, "user", None)
        return owner is not None and getattr(owner, "id", None) == user.id
