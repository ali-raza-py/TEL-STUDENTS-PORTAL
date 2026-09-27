from __future__ import annotations

from django.conf import settings
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class TelPagination(PageNumberPagination):
    """Standard, client-controllable page size with sane bounds."""

    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "num_pages": self.page.paginator.num_pages,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "has_next": self.page.has_next(),
                "has_previous": self.page.has_previous(),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


class LargePagination(TelPagination):
    max_page_size = 200


def page_size_from_request(request) -> int:
    try:
        return int(request.query_params.get(settings.PAGE_SIZE_QUERY_PARAM, 12))
    except (TypeError, ValueError):
        return 12
