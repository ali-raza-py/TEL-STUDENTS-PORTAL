from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", views.PasswordForgotView.as_view(), name="password-forgot"),
    path("password/reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("roles/", views.RoleListView.as_view(), name="roles"),
]
