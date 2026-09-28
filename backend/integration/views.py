from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from academics.selectors import resolve_student_scope
from core.dashboard import build_dashboard
from core.staff_dashboard import build_admin_dashboard, build_teacher_dashboard


class DashboardView(APIView):
    """
    The single endpoint behind the dashboard.

    The payload is role shaped. Students and class representatives get their own
    academic overview; teachers get their teaching load and review queues;
    administrators get the institution wide picture. Every value is computed
    from TEL data, and missing data is reported as an explicit empty state
    rather than filled in with a plausible number.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_superuser or user.role == Role.ADMIN:
            return Response(build_admin_dashboard(user=user))
        if user.role == Role.TEACHER:
            return Response(build_teacher_dashboard(user=user))

        scope = resolve_student_scope(user, required=False)
        if scope is None:
            return Response(
                {
                    "available": False,
                    "reason": "no_student_profile",
                    "message": (
                        "This account is not linked to a student record. "
                        "Please contact your TEL class teacher."
                    ),
                }
            )
        if not scope.is_complete:
            return Response(
                {
                    "available": False,
                    "reason": "incomplete_placement",
                    "message": (
                        "Your class placement is incomplete, so academic data cannot be shown yet."
                    ),
                }
            )
        return Response(build_dashboard(user=user, scope=scope))
