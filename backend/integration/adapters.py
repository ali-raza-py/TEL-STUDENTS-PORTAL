"""
TEL core integration layer.

TEL's existing management system stays the source of truth. The student portal
never reads TEL's production database directly; it consumes authorised data
through this adapter, which can be swapped without touching the API surface or
the frontend.

Three adapters ship:

* ``LocalMirrorAdapter``  — data already synchronised into the portal database
  (the default for development and for an eventual read replica).
* ``HttpTelAdapter``     — calls the TEL core REST API with a service key.
* ``CompositeAdapter``   — prefers the HTTP source and falls back to the local
  mirror, so a TEL outage degrades instead of blanking the portal.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from django.conf import settings

logger = logging.getLogger("telportal.integration")


@dataclass
class SyncOutcome:
    entity: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated


@dataclass
class IntegrationStatus:
    adapter: str
    healthy: bool
    mode: str
    message: str
    last_synced_at: datetime | None = None
    entities: list[str] = field(default_factory=list)


class FieldMapper:
    """
    Translates TEL core field names into portal field names.

    Kept configurable so a change in TEL's payload shape is a config edit rather
    than a code change in the sync path.
    """

    DEFAULT_MAPPINGS: dict[str, dict[str, str]] = {
        "student": {
            "full_name": "full_name",
            "name": "full_name",
            "email": "email",
            "roll_no": "roll_number",
            "campus": "campus",
            "program": "program",
            "class": "class_room",
            "section": "section",
            "year": "academic_year",
            "guardian_contact": "guardian_phone",
        },
        "attendance": {
            "date": "date",
            "subject": "subject",
            "subject_code": "subject",
            "present": "status",
            "absent": "status",
        },
        "result": {
            "marks_obtained": "obtained_marks",
            "obtained": "obtained_marks",
            "total": "total_marks",
            "max_marks": "total_marks",
            "subject": "subject",
            "exam": "assessment_name",
            "date": "assessment_date",
        },
        "paper": {
            "title": "title",
            "subject": "subject",
            "type": "exam_type",
            "total_marks": "total_marks",
            "date": "exam_date",
            "file": "paper_file",
        },
        "timetable": {
            "day": "day_of_week",
            "start": "start_time",
            "end": "end_time",
            "subject": "subject",
            "room": "room",
        },
    }

    def __init__(self, mappings: dict[str, dict[str, str]] | None = None):
        self.mappings = mappings or self.DEFAULT_MAPPINGS

    def map(self, entity: str, record: dict) -> dict:
        table = self.mappings.get(entity, {})
        return {table.get(k, k): v for k, v in record.items()}


class TelSourceAdapter(ABC):
    """The contract the portal depends on."""

    name = "base"
    mode = "unknown"

    @abstractmethod
    def status(self) -> IntegrationStatus: ...

    @abstractmethod
    def fetch(self, entity: str, **params) -> Iterable[dict]: ...

    def available_entities(self) -> list[str]:
        return ["student", "attendance", "result", "paper", "timetable", "announcement", "resource"]


class LocalMirrorAdapter(TelSourceAdapter):
    """
    Reads from the portal's own database.

    This is the mirror that the sync job writes into; the portal then serves it
    with normal, fast, well-indexed queries.
    """

    name = "local"
    mode = "local mirror"

    def status(self) -> IntegrationStatus:
        from django.db import connection

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            healthy = True
            message = "Reading from the local TEL data mirror."
        except Exception as exc:  # pragma: no cover - infrastructure path
            healthy = False
            message = f"Local mirror unavailable: {exc.__class__.__name__}"
        return IntegrationStatus(
            adapter=self.name, healthy=healthy, mode=self.mode, message=message,
            entities=self.available_entities(),
        )

    def fetch(self, entity: str, **params) -> Iterable[dict]:
        """
        The mirror *is* the portal database, so the sync job is a no-op here.
        The method exists so callers do not have to special-case the adapter.
        """

        return ()


class HttpTelAdapter(TelSourceAdapter):
    """Talks to the TEL core REST API using a service key."""

    name = "http"
    mode = "TEL core API"

    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "TEL-Student-Portal/1.0",
        }

    def _get(self, path: str, params: dict | None = None) -> Any:
        import urllib.error
        import urllib.parse
        import urllib.request

        if not self.configured:
            raise TelIntegrationUnavailable("TEL core API is not configured.")
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                import json

                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TelIntegrationError(f"TEL core returned {exc.code} for {path}") from exc
        except Exception as exc:  # pragma: no cover - network path
            raise TelIntegrationError(f"Could not reach TEL core: {exc.__class__.__name__}") from exc

    def status(self) -> IntegrationStatus:
        if not self.configured:
            return IntegrationStatus(
                adapter=self.name,
                healthy=False,
                mode=self.mode,
                message=(
                    "TEL_CORE_API_BASE_URL and TEL_CORE_API_KEY are not set. "
                    "The portal is serving its local mirror."
                ),
                entities=self.available_entities(),
            )
        try:
            self._get("health")
            return IntegrationStatus(
                adapter=self.name, healthy=True, mode=self.mode,
                message="Connected to the TEL core API.", entities=self.available_entities(),
            )
        except TelIntegrationUnavailable as exc:
            return IntegrationStatus(
                adapter=self.name, healthy=False, mode=self.mode, message=str(exc),
                entities=self.available_entities(),
            )
        except TelIntegrationError as exc:
            return IntegrationStatus(
                adapter=self.name, healthy=False, mode=self.mode, message=str(exc),
                entities=self.available_entities(),
            )

    def fetch(self, entity: str, **params) -> Iterable[dict]:
        payload = self._get(f"students/{entity}/" if entity == "student" else f"{entity}/", params)
        if isinstance(payload, dict):
            rows = payload.get("results") or payload.get("data") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        return rows


class CompositeAdapter(TelSourceAdapter):
    """Prefers the live TEL API, falls back to the local mirror."""

    name = "composite"
    mode = "TEL core API with local mirror fallback"

    def __init__(self, primary: TelSourceAdapter, fallback: TelSourceAdapter):
        self.primary = primary
        self.fallback = fallback

    def status(self) -> IntegrationStatus:
        primary = self.primary.status()
        if primary.healthy:
            return primary
        fallback = self.fallback.status()
        return IntegrationStatus(
            adapter=self.name,
            healthy=fallback.healthy,
            mode=self.mode,
            message=(
                f"{primary.message} Falling back to the local mirror."
                if fallback.healthy
                else primary.message
            ),
            entities=self.available_entities(),
        )

    def fetch(self, entity: str, **params) -> Iterable[dict]:
        try:
            return self.primary.fetch(entity, **params)
        except (TelIntegrationError, TelIntegrationUnavailable) as exc:
            logger.warning("TEL primary fetch failed for %s: %s", entity, exc)
            return self.fallback.fetch(entity, **params)


class TelIntegrationError(RuntimeError):
    """Raised when TEL core cannot be read."""


class TelIntegrationUnavailable(TelIntegrationError):
    """Raised when the integration is not configured."""


_ADAPTERS: dict[str, type[TelSourceAdapter]] = {
    "local": LocalMirrorAdapter,
    "http": HttpTelAdapter,
}


def get_adapter() -> TelSourceAdapter:
    name = (settings.TEL_INTEGRATION_ADAPTER or "local").lower()
    mapper = FieldMapper()

    if name == "http":
        adapter: TelSourceAdapter = HttpTelAdapter(
            base_url=settings.TEL_CORE_API_BASE_URL,
            api_key=settings.TEL_CORE_API_KEY,
            timeout=settings.TEL_CORE_API_TIMEOUT,
        )
    else:
        adapter = _ADAPTERS.get(name, LocalMirrorAdapter)()

    adapter.field_mapper = mapper  # type: ignore[attr-defined]
    return adapter


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None
