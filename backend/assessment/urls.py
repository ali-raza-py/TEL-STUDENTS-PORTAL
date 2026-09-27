from django.urls import path

from assessment import views

app_name = "assessment"

urlpatterns = [
    # Paper archive (student)
    path("student/papers/", views.StudentPaperListView.as_view(), name="student-papers"),
    path("papers/<int:pk>/", views.PaperDetailView.as_view(), name="paper-detail"),
    path("papers/<int:pk>/practice/", views.StartPracticeView.as_view(), name="paper-practice"),
    # Practice engine
    path("practice/<int:pk>/save/", views.SavePracticeProgressView.as_view(), name="practice-save"),
    path("practice/<int:pk>/submit/", views.SubmitPracticeView.as_view(), name="practice-submit"),
    path("practice/<int:pk>/review/", views.PracticeReviewView.as_view(), name="practice-review"),
    path("student/practice-history/", views.PracticeHistoryView.as_view(), name="practice-history"),
    # Results
    path("student/results/", views.StudentResultListView.as_view(), name="student-results"),
    path("student/analytics/", views.StudentAnalyticsView.as_view(), name="student-analytics"),
    path("student/analytics/topics/", views.TopicAnalysisView.as_view(), name="topic-analysis"),
    path("student/progress/", views.ProgressSummaryView.as_view(), name="progress-summary"),
    # Reference data
    path("exam-types/", views.ExamTypeListView.as_view(), name="exam-types"),
    path("result-statuses/", views.ResultStatusListView.as_view(), name="result-statuses"),
    # Staff surface
    path("manage/papers/", views.PaperListView.as_view(), name="manage-papers"),
    path("manage/papers/create/", views.ManagePaperCreateView.as_view(), name="manage-paper-create"),
    path("manage/papers/<int:pk>/questions/", views.ManagePaperQuestionView.as_view(), name="manage-paper-questions"),
    path("manage/papers/<int:pk>/transition/", views.ManagePaperTransitionView.as_view(), name="manage-paper-transition"),
    path("manage/results/", views.ManageResultListCreateView.as_view(), name="manage-results"),
    path("manage/results/<int:pk>/transition/", views.ManageResultTransitionView.as_view(), name="manage-result-transition"),
    path("manage/students/", views.StudentRegisterView.as_view(), name="manage-students"),
]
