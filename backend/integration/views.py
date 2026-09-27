from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.selectors import resolve_student_scope
from core.dashboard import build_dashboard


class DashboardView(APIView):
    """
    The single endpoint behind the dashboard.

    Every value is computed from TEL data. Missing data is reported as an
    explicit empty state rather than filled in with a plausible number.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = resolve_student_scope(request.user, required=False)
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
        return Response(build_dashboard(user=request.user, scope=scope))
