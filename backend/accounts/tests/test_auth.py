"""Authentication: cookie sessions, rejection, logout, passwords, enumeration."""

from __future__ import annotations

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import override_settings

from accounts.models import User
from common.tests.base import ApiTestCase
from common.tests.factories import DEMO_PASSWORD, build_class, make_admin, make_student
from core.models import AuditLog

NEW_PASSWORD = "Lantern-River-Stand-77"


class LoginTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.user = self.profile.user

    def test_login_with_valid_credentials_sets_httponly_cookies_and_returns_the_user(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": DEMO_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        # Both JWT cookies are set, HttpOnly, and carry a token.
        for cookie_name in (settings.ACCESS_COOKIE_NAME, settings.REFRESH_COOKIE_NAME):
            self.assertIn(cookie_name, response.cookies)
            cookie = response.cookies[cookie_name]
            self.assertTrue(cookie.value, f"{cookie_name} was set empty")
            self.assertEqual(cookie["httponly"], True)
            self.assertEqual(cookie["path"], "/")

        body = response.json()
        self.assertEqual(body["user"]["email"], self.user.email)
        self.assertEqual(body["user"]["full_name"], self.user.full_name)
        self.assertEqual(body["user"]["role"], "STUDENT")
        self.assertEqual(body["user"]["student_profile"]["student_code"], self.profile.student_code)
        self.assertIn("view_dashboard", body["user"]["capabilities"])
        self.assertEqual(body["access_expires_in"], 30 * 60)

        # The cookies really authenticate: a protected read succeeds with them.
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], self.user.email)

    def test_login_is_case_insensitive_on_the_email(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email.upper(), "password": DEMO_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], self.user.email)

    def test_login_with_a_wrong_password_is_rejected_and_creates_no_session(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": "not-the-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertEqual(body["error"]["message"], "We could not verify those sign-in details.")

        # No credential is handed out, and no Django session is created.
        self.assertNotIn(settings.ACCESS_COOKIE_NAME, response.cookies)
        self.assertNotIn(settings.REFRESH_COOKIE_NAME, response.cookies)
        self.assertEqual(Session.objects.count(), 0)

        # The attempt is recorded without disclosing the stored hash.
        entry = AuditLog.objects.get(action="auth.login_failed")
        self.assertEqual(entry.metadata["email"], self.user.email)
        self.assertNotIn("password", entry.metadata)

        # And the rejected client is still anonymous.
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_login_with_an_inactive_account_is_rejected(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": DEMO_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(settings.ACCESS_COOKIE_NAME, response.cookies)
        self.assertEqual(Session.objects.count(), 0)


class LogoutTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.user = make_student(self.graph, index=1).user

    def test_logout_clears_the_auth_cookies_and_ends_the_session(self):
        self.sign_in(self.user)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        response = self.sign_out()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "Signed out.")
        for cookie_name in (settings.ACCESS_COOKIE_NAME, settings.REFRESH_COOKIE_NAME):
            self.assertIn(cookie_name, response.cookies)
            cookie = response.cookies[cookie_name]
            self.assertEqual(cookie.value, "", f"{cookie_name} was not cleared")
            self.assertEqual(cookie["max-age"], 0)

        # The cleared cookies are dropped from the client jar.
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="auth.logout", actor=self.user).exists())


class UnauthenticatedAccessTests(ApiTestCase):
    def test_anonymous_access_to_a_protected_endpoint_returns_401(self):
        for path in ("/api/auth/me/", "/api/student/results/", "/api/notifications/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["error"]["code"], "not_authenticated")
                self.assertIn("WWW-Authenticate", response)

    def test_anonymous_write_requests_are_rejected_with_401(self):
        response = self.client.post(
            "/api/auth/password/change/",
            {"current_password": DEMO_PASSWORD, "new_password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "not_authenticated")


class PasswordChangeTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.user = make_student(self.graph, index=1).user

    def test_password_change_requires_the_correct_current_password(self):
        self.sign_in(self.user)

        rejected = self.client.post(
            "/api/auth/password/change/",
            {"current_password": "wrong-current-password", "new_password": NEW_PASSWORD},
            format="json",
        )

        self.assertEqual(rejected.status_code, 400)
        details = rejected.json()["error"]["details"]
        self.assertIn("current_password", details)
        self.assertEqual(str(details["current_password"][0]), "Your current password is incorrect.")

        # The stored password is untouched: the old one still works, new does not.
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEMO_PASSWORD))
        self.assertFalse(self.user.check_password(NEW_PASSWORD))
        self.assertIsNone(self.user.password_changed_at)
        self.assertFalse(AuditLog.objects.filter(action="auth.password_changed").exists())

    def test_password_change_succeeds_with_the_correct_current_password(self):
        self.sign_in(self.user)

        response = self.client.post(
            "/api/auth/password/change/",
            {"current_password": DEMO_PASSWORD, "new_password": NEW_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["detail"], "Password updated.")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(DEMO_PASSWORD))
        self.assertIsNotNone(self.user.password_changed_at)
        self.assertTrue(AuditLog.objects.filter(action="auth.password_changed", actor=self.user).exists())

        # The old password no longer opens a session; the new one does.
        self.client = self.client_class()
        self.assertEqual(
            self.client.post(
                "/api/auth/login/",
                {"email": self.user.email, "password": DEMO_PASSWORD},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/login/",
                {"email": self.user.email, "password": NEW_PASSWORD},
                format="json",
            ).status_code,
            200,
        )

    def test_a_weak_new_password_is_refused(self):
        self.sign_in(self.user)

        response = self.client.post(
            "/api/auth/password/change/",
            {"current_password": DEMO_PASSWORD, "new_password": "1234"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json()["error"]["details"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEMO_PASSWORD))


class PasswordResetRequestTests(ApiTestCase):
    """The reset request must not disclose whether an account exists."""

    def setUp(self):
        self.graph = build_class()
        self.user = make_student(self.graph, index=1).user
        self.admin = make_admin()

    def test_the_response_is_identical_for_a_known_and_an_unknown_address(self):
        known = self.client.post(
            "/api/auth/password/forgot/", {"email": self.user.email}, format="json"
        )
        unknown = self.client.post(
            "/api/auth/password/forgot/",
            {"email": "nobody.here@student.tel.edu.pk"},
            format="json",
        )

        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(
            known.json()["detail"],
            "If an account exists for that address, a reset link has been sent.",
        )
        # No user object, token or trace detail differs between the two answers.
        self.assertEqual(sorted(known.json().keys()), ["detail"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_a_reset_link_is_issued_only_for_a_real_account(self):
        self.client.post(
            "/api/auth/password/forgot/", {"email": self.user.email}, format="json"
        )
        self.client.post(
            "/api/auth/password/forgot/",
            {"email": "nobody.here@student.tel.edu.pk"},
            format="json",
        )

        actions = list(
            AuditLog.objects.filter(action="auth.password_reset_requested").values_list(
                "metadata", flat=True
            )
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["email"], self.user.email)
        self.assertTrue(actions[0]["token"])

    def test_a_bogus_reset_token_is_rejected(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        response = self.client.post(
            "/api/auth/password/reset/",
            {
                "token": f"{urlsafe_base64_encode(force_bytes(self.user.pk))}-not-a-real-token",
                "new_password": NEW_PASSWORD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["message"],
            "This reset link is no longer valid. Please request a new one.",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEMO_PASSWORD))
