from __future__ import annotations

import logging
from typing import Any

from django.db.models import Model

from core.models import AuditLog

logger = logging.getLogger("telportal.audit")

#: Values that must never reach the audit trail verbatim.
_SENSITIVE_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "refresh",
    "access",
    "authorization",
    "api_key",
    "secret",
    "otp",
}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[redacted]" if k.lower() in _SENSITIVE_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


def log_event(
    request,
    *,
    action: str,
    user=None,
    entity: Model | None = None,
    entity_id: str | int | None = None,
    entity_type: str | None = None,
    summary: str = "",
    metadata: dict | None = None,
) -> AuditLog | None:
    """Write an audit entry. Never raises — auditing must not break a request."""

    try:
        actor = user
        if actor is None and request is not None:
            candidate = getattr(request, "user", None)
            if candidate is not None and getattr(candidate, "is_authenticated", False):
                actor = candidate

        if entity is not None:
            entity_type = entity_type or entity.__class__.__name__
            if entity_id is None:
                entity_id = getattr(entity, "public_id", None) or entity.pk

        return AuditLog.objects.create(
            actor=actor if (actor is not None and getattr(actor, "pk", None)) else None,
            actor_role=getattr(actor, "role", "") or "SYSTEM",
            action=action[:64],
            entity_type=(entity_type or "")[:64],
            entity_id=str(entity_id or "")[:64],
            summary=summary[:240],
            metadata=_scrub(metadata or {}),
            ip_address=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:240],
        )
    except Exception:  # pragma: no cover - auditing is best effort
        logger.warning("Audit write failed for action %s", action, exc_info=True)
        return None
