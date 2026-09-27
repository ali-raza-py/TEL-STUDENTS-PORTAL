from django.urls import path

from engagement import views

app_name = "engagement"

urlpatterns = [
    # Attendance
    path("student/attendance/", views.StudentAttendanceView.as_view(), name="student-attendance"),
    path("student/attendance/records/", views.StudentAttendanceRecordsView.as_view(), name="student-attendance-records"),
    # Assignments
    path("student/assignments/", views.StudentAssignmentListView.as_view(), name="student-assignments"),
    path("assignments/<int:pk>/submissions/", views.AssignmentSubmissionCreateView.as_view(), name="assignment-submissions"),
    # Resources
    path("student/resources/", views.ResourceListView.as_view(), name="student-resources"),
    path("resources/<int:pk>/", views.ResourceDetailView.as_view(), name="resource-detail"),
    # Announcements
    path("student/announcements/", views.AnnouncementListView.as_view(), name="student-announcements"),
    path("manage/announcements/", views.AnnouncementManageView.as_view(), name="manage-announcements"),
    # Calendar
    path("student/calendar/", views.AcademicCalendarView.as_view(), name="student-calendar"),
    path("manage/events/", views.AcademicEventManageView.as_view(), name="manage-events"),
    # Requests
    path("student/requests/", views.StudentRequestListCreateView.as_view(), name="student-requests"),
    path("manage/requests/<int:pk>/", views.StaffRequestUpdateView.as_view(), name="manage-request"),
    # Feedback
    path("student/feedback/", views.StudentFeedbackView.as_view(), name="student-feedback"),
]
