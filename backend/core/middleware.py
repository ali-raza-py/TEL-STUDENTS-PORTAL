"""
Request level infrastructure: a request context (for logging and rate limiting)
and a lightweight sliding-window rate limiter.

The limiter is a per-process fixed-window counter keyed by authenticated user
when available and by client IP otherwise. It is intentionally dependency free;
a multi-process deployment should swap ``TEL_RATE_LIMIT_STORE`` for Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from django.conf import settings
from django.http import JsonResponse


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tel_request_id = request.META.get("HTTP_X_TEL_TRACE") or None
        response = self.get_response(request)
        if request.tel_request_id:
            response["X-Tel-Trace"] = request.tel_request_id
        return response


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


limiter = SlidingWindowLimiter()


def _parse_rate(rate: str) -> tuple[int, int]:
    """Parses ``"1200/min"`` into ``(count, seconds)``."""

    if "/" not in rate:
        return int(rate), 60
    count, _, suffix = rate.partition("/")
    suffix = suffix.strip().lower()
    seconds = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hour": 3600, "d": 86400}.get(
        suffix, 60
    )
    return max(1, int(count)), seconds


def _bucket_for(request) -> str:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"u:{user.pk}"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


class ApiRateLimitMiddleware:
    """Applies coarse per-route rate limits to the API surface."""

    EXEMPT_PREFIXES = ("/api/health/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.RATE_LIMIT_ENABLED and request.path.startswith("/api/"):
            if not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
                limit_name, rate = self._resolve(request)
                if rate:
                    count, window = _parse_rate(rate)
                    key = f"{limit_name}:{_bucket_for(request)}"
                    allowed, retry_after = limiter.hit(key, count, window)
                    if not allowed:
                        response = JsonResponse(
                            {
                                "error": {
                                    "code": "throttled",
                                    "message": "Too many requests. Please slow down and try again shortly.",
                                    "details": {"retry_after": retry_after},
                                    "trace_id": None,
                                }
                            },
                            status=429,
                        )
                        response["Retry-After"] = str(retry_after)
                        return response
        return self.get_response(request)

    @staticmethod
    def _resolve(request) -> tuple[str, str]:
        limits = settings.TEL_RATE_LIMITS
        path = request.path
        if path.startswith("/api/auth/"):
            return "auth", limits["auth"]
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and "upload" in path:
            return "upload", limits["upload"]
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            return "write", limits["write"]
        return "api", limits["api"]
