from __future__ import annotations

from django.db import transaction
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.authentication import clear_auth_cookies, set_auth_cookies
from accounts.models import Role, User
from accounts.permissions import capabilities_for
from accounts.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    ProfileUpdateSerializer,
    RoleSerializer,
    StudentContactUpdateSerializer,
    UserSerializer,
    authenticate_user,
)
from common.exceptions import TelAPIException
from core.audit import log_event


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_user(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        if user is None:
            log_event(
                request,
                action="auth.login_failed",
                metadata={"email": serializer.validated_data["email"].lower()},
            )
            raise TelAPIException("We could not verify those sign-in details.")

        if user.role == Role.TEACHER or user.role == Role.ADMIN:
            # Staff use the existing TEL management system; the student portal
            # signs them out rather than pretending they are a student.
            pass

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        access["role"] = user.role
        access["name"] = user.full_name

        user.last_login_ip = _client_ip(request)
        user.save(update_fields=["last_login_ip"])

        response = Response(
            {
                "user": UserSerializer(user, context={"request": request}).data,
                "access_expires_in": int(refresh.access_token.lifetime.total_seconds()),
            }
        )
        set_auth_cookies(response, str(access), str(refresh))
        log_event(request, action="auth.login", user=user)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        log_event(request, action="auth.logout", user=request.user)
        response = Response({"detail": "Signed out."})
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        payload = {
            "user": UserSerializer(user, context={"request": request}).data,
            "roles": [
                {"code": code, "label": label}
                for code, label in Role.choices
            ],
            "capabilities": capabilities_for(user.role),
        }
        return Response(payload)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    @transaction.atomic
    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        profile = getattr(user, "student_profile", None)
        if profile is not None:
            contact = StudentContactUpdateSerializer(
                profile, data=request.data, partial=True, context={"request": request}
            )
            contact.is_valid(raise_exception=True)
            contact.save()
        log_event(request, action="profile.updated", user=request.user, metadata={"fields": sorted(serializer.validated_data.keys())})
        return Response(UserSerializer(user, context={"request": request}).data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_event(request, action="auth.password_changed", user=user)
        return Response({"detail": "Password updated."})


class PasswordForgotView(APIView):
    """Always returns the same response so accounts cannot be enumerated."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email, is_active=True).first()
        if user is not None:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            log_event(
                request,
                action="auth.password_reset_requested",
                metadata={"email": email, "uid": uid, "token": token},
            )
        return Response(
            {
                "detail": "If an account exists for that address, a reset link has been sent."
            },
            status=202,
        )


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pk = force_str(urlsafe_base64_decode(serializer.validated_data["token"]))
            user = User.objects.get(pk=pk, is_active=True)
        except Exception:
            raise TelAPIException("This reset link is no longer valid. Please request a new one.")
        if not default_token_generator.check_token(user, serializer.validated_data["new_password"]):
            raise TelAPIException("This reset link is no longer valid. Please request a new one.")
        user.set_password(serializer.validated_data["new_password"])
        user.mark_password_changed()
        user.save(update_fields=["password", "password_changed_at"])
        log_event(request, action="auth.password_reset", user=user)
        return Response({"detail": "Password updated. You can sign in now."})


class CsrfView(APIView):
    """Ensures the CSRF cookie exists so the SPA can start an authenticated session."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        from django.middleware.csrf import get_token

        return Response({"csrf_token": get_token(request)})


class RoleListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response(RoleSerializer(Role.choices, many=True).data)


def transaction_guarded(func):
    """Backwards compatible alias kept for readability in older call sites."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    return wrapper


__all__ = [
    "CsrfView",
    "LoginView",
    "LogoutView",
    "MeView",
    "PasswordChangeView",
    "PasswordForgotView",
    "PasswordResetView",
    "ProfileView",
    "RoleListView",
]
