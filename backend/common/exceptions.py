"""
A single, predictable error envelope for the whole API.

Every failure — validation, permission, throttling or unexpected — is returned
in the same shape so the frontend can map it to a user friendly message without
guessing:

    {
      "error": {
        "code": "validation_error",
        "message": "Please correct the highlighted fields.",
        "details": {"email": ["This field is required."]},
        "trace_id": "3f1c..."      # safe to show, useful in support tickets
      }
    }

Internal exception text is never echoed to the client; it is logged with the
same ``trace_id`` instead.
"""

from __future__ import annotations

import logging
import uuid

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("telportal.api")

MESSAGES = {
    "validation_error": "Please correct the highlighted fields.",
    "not_authenticated": "Your session has expired. Please sign in again.",
    "authentication_failed": "We could not verify those sign-in details.",
    "permission_denied": "You do not have permission to perform this action.",
    "not_found": "The requested record could not be found.",
    "method_not_allowed": "That action is not available for this endpoint.",
    "throttled": "Too many requests. Please slow down and try again shortly.",
    "conflict": "That change conflicts with the current state of the data.",
    "server_error": "Something went wrong on our side. Please try again.",
}


def _envelope(code: str, message: str, details=None, trace_id: str | None = None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": trace_id,
        }
    }


def tel_exception_handler(exc, context):
    trace_id = uuid.uuid4().hex[:12]
    request = context.get("request")

    if isinstance(exc, Throttled):
        wait = int(getattr(exc, "wait", 0) or 0)
        response = Response(
            _envelope("throttled", MESSAGES["throttled"], {"retry_after": wait}, trace_id),
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(wait)
        return response

    if isinstance(exc, Http404):
        return Response(
            _envelope("not_found", MESSAGES["not_found"], trace_id=trace_id),
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            _envelope("permission_denied", MESSAGES["permission_denied"], trace_id=trace_id),
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, DjangoValidationError):
        return Response(
            _envelope(
                "validation_error",
                MESSAGES["validation_error"],
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages},
                trace_id,
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, IntegrityError):
        logger.warning("Integrity error [%s] on %s", trace_id, request, exc_info=True)
        return Response(
            _envelope("conflict", MESSAGES["conflict"], trace_id=trace_id),
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, APIException):
        response = drf_exception_handler(exc, context)
        if response is None:
            return None
        code = getattr(exc, "default_code", "error")
        message = _humanise(exc)
        details = response.data if isinstance(response.data, dict) else {"detail": response.data}
        response.data = _envelope(code, message, details, trace_id)
        return response

    logger.exception("Unhandled API exception [%s] on %s", trace_id, request, exc_info=exc)
    return Response(
        _envelope("server_error", MESSAGES["server_error"], trace_id=trace_id),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _humanise(exc: APIException) -> str:
    if isinstance(exc.detail, str):
        return exc.detail
    default_code = getattr(exc, "default_code", "")
    if default_code == "not_authenticated":
        return MESSAGES["not_authenticated"]
    if default_code == "permission_denied":
        return MESSAGES["permission_denied"]
    if default_code == "not_found":
        return MESSAGES["not_found"]
    if default_code == "authentication_failed":
        return MESSAGES["authentication_failed"]
    return MESSAGES["validation_error"]


class TelAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = MESSAGES["validation_error"]
    default_code = "validation_error"


class Conflict(TelAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = MESSAGES["conflict"]
    default_code = "conflict"


class Forbidden(TelAPIException):
    """403 — the caller is authenticated but not allowed to do this."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = MESSAGES["permission_denied"]
    default_code = "permission_denied"


class InvalidWorkflowTransition(TelAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "That action is not allowed from the current state."
    default_code = "invalid_workflow_transition"
