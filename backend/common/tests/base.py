"""
Base test cases.

Two deliberate deviations from the deployed configuration:

* ``TEL_RATE_LIMITS`` is raised so a burst of requests inside one test process
  cannot be throttled. Rate limiting itself is not under test, but the
  middleware still runs on every request.
* The in-process sliding window and the ``locmem`` cache are reset around each
  test so no state leaks between tests regardless of execution order.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from core.middleware import limiter

NO_THROTTLE_LIMITS = {
    "api": "100000/min",
    "session": "100000/min",
    "auth": "100000/min",
    "write": "100000/min",
    "upload": "100000/min",
}


class PortalTestMixin:
    """Guarantees per-test isolation of the in-process caches."""

    def setUp(self):
        super().setUp()
        limiter.reset()
        cache.clear()
        self.addCleanup(limiter.reset)
        self.addCleanup(cache.clear)

    # -- request helpers ---------------------------------------------------

    def as_user(self, user):
        """Authenticates ``self.client`` as ``user`` for the rest of the test."""

        self.client.force_authenticate(user=user)
        return self.client

    def sign_in(self, user, *, password: str | None = None):
        """Signs in through the real login endpoint and keeps the cookies."""

        from common.tests.factories import DEMO_PASSWORD

        response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": password or DEMO_PASSWORD},
            format="json",
        )
        self.assertEqual(
            response.status_code, 200, msg=f"login failed for {user.email}: {response.content}"
        )
        return response

    def sign_out(self):
        return self.client.post("/api/auth/logout/", format="json")


@override_settings(TEL_RATE_LIMITS=NO_THROTTLE_LIMITS)
class ApiTestCase(PortalTestMixin, APITestCase):
    """API level tests. ``self.client`` is a ``rest_framework.test.APIClient``."""


@override_settings(TEL_RATE_LIMITS=NO_THROTTLE_LIMITS)
class ServiceTestCase(PortalTestMixin, TestCase):
    """Tests that exercise a service / selector module directly."""

    client_class = APIClient
