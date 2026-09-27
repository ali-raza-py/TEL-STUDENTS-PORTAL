"""
JWT authentication delivered as ``HttpOnly`` cookies.

Why cookies rather than ``localStorage``:
  * The access token is not reachable from JavaScript, so an XSS payload cannot
    exfiltrate a long lived credential.
  * Unsafe requests (POST/PUT/PATCH/DELETE) additionally have to echo the CSRF
    cookie in the ``X-TEL-CSRFToken`` header, which is checked with Django's own
    CSRF machinery so token rotation and masking behave exactly as they do for
    session-authenticated form views.

A standard ``Authorization: Bearer <token>`` header is still accepted so that
server-to-server and integration tests can authenticate without cookies.
"""

from __future__ import annotations

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class _CsrfCheck(CsrfViewMiddleware):
    """Runs Django's CSRF verification without a response phase."""

    def _reject(self, request, reason):  # pragma: no cover - defensive
        return reason


def _csrf_reject_response(reason):  # pragma: no cover - used for readability
    return reason


class CookieJWTAuthentication(JWTAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None
        from_cookie = False

        if header is None:
            raw_token = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
            from_cookie = raw_token is not None
        else:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        if from_cookie and request.method.upper() not in SAFE_METHODS:
            _enforce_csrf(request)

        return user, validated_token


def _enforce_csrf(request) -> None:
    checker = _CsrfCheck(lambda r: None)
    checker.process_request(request)
    reason = checker.process_view(request, None, (), {})
    if reason is not None:
        raise exceptions.PermissionDenied(
            _("CSRF verification failed. Refresh the page and try again."),
            code="csrf_failed",
        )


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": settings.SESSION_COOKIE_SAMESITE if hasattr(settings, "SESSION_COOKIE_SAMESITE") else "Lax",
        "path": "/",
    }
    response.set_cookie(
        settings.ACCESS_COOKIE_NAME,
        access_token,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )


def clear_auth_cookies(response) -> None:
    for name in (settings.ACCESS_COOKIE_NAME, settings.REFRESH_COOKIE_NAME):
        response.delete_cookie(name, path="/")
