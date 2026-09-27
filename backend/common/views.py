from __future__ import annotations

from django.db import connection
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness / readiness probe used by the SPA and by deployment platforms."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        database_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:  # pragma: no cover - infrastructure failure path
            database_ok = False

        payload = {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "service": "tel-student-portal-api",
        }
        return Response(payload, status=status.HTTP_200_OK if database_ok else 503)


class ApiRootView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response(
            {
                "service": "TEL Education Link Student Portal API",
                "version": "1.0.0",
                "documentation": "See README.md for the endpoint overview.",
            }
        )


api_root = ApiRootView.as_view()


def q_or(*args: Q) -> Q:
    result = Q()
    for arg in args:
        result |= arg
    return result
