from __future__ import annotations

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integration.adapters import get_adapter


class IntegrationStatusView(APIView):
    """
    Reports which TEL source is serving the portal.

    Deliberately available to signed-in users so support can tell whether a
    student is looking at fresh TEL data or a local mirror — but it exposes no
    URLs, keys or host details.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        adapter = get_adapter()
        status = adapter.status()
        return Response(
            {
                "adapter": status.adapter,
                "mode": status.mode,
                "healthy": status.healthy,
                "message": status.message,
                "entities": status.entities,
            }
        )


class MappingProfileView(APIView):
    """The field mapping the sync job uses — documentation, not secrets."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounts.models import Role
        from common.exceptions import TelAPIException, Forbidden

        if request.user.role != Role.ADMIN and not request.user.is_superuser:
            raise Forbidden("Only a TEL administrator can view the mapping profile.")
        from integration.adapters import FieldMapper

        return Response({"mappings": FieldMapper.DEFAULT_MAPPINGS})
