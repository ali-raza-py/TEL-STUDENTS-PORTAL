"""Root URL configuration for the TEL Student Portal backend."""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from common.views import HealthView, api_root

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api_root, name="api-root"),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("academics.urls")),
    path("api/", include("assessment.urls")),
    path("api/", include("engagement.urls")),
    path("api/", include("core.urls")),
    path("api/", include("integration.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "TEL Education Link Administration"
admin.site.site_title = "TEL Administration"
admin.site.index_title = "TEL core system"
