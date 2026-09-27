from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/unread-count/", views.NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("lookups/", views.LookupDataView.as_view(), name="lookups"),
    path("class-toolkit/", views.ClassToolkitView.as_view(), name="class-toolkit"),
    path("files/<int:pk>/", views.FileAccessView.as_view(), name="file-access"),
    path("audit-log/", views.AuditLogListView.as_view(), name="audit-log"),
]
