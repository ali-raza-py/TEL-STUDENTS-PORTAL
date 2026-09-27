from django.urls import path

from academics import views

app_name = "academics"

urlpatterns = [
    path("class/", views.StudentClassView.as_view(), name="student-class"),
    path("catalogue/", views.CatalogueView.as_view(), name="catalogue"),
    path("subjects/", views.SubjectListView.as_view(), name="subjects"),
    path("subjects/all/", views.SubjectCatalogueView.as_view(), name="subject-catalogue"),
    path("timetable/", views.TimetableView.as_view(), name="timetable"),
    path("timetable/today/", views.TimetableTodayView.as_view(), name="timetable-today"),
    path("timetable/versions/", views.TimetableVersionView.as_view(), name="timetable-versions"),
    path("timetable/submissions/", views.TimetableSubmissionListCreateView.as_view(), name="timetable-submissions"),
    path("timetable/submissions/<int:pk>/review/", views.TimetableSubmissionReviewView.as_view(), name="timetable-review"),
    path("timetable/submissions/<int:pk>/publish/", views.TimetableSubmissionPublishView.as_view(), name="timetable-publish"),
    path("admin/class-representatives/", views.ClassRepresentativeView.as_view(), name="class-representatives"),
]
