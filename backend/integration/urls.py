from django.urls import path

from integration import status as integration_status
from integration.views import DashboardView

app_name = "integration"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("integration/status/", integration_status.IntegrationStatusView.as_view(), name="integration-status"),
    path("integration/mapping/", integration_status.MappingProfileView.as_view(), name="integration-mapping"),
]
