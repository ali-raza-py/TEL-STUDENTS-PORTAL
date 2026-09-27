"""
Audit trail: sensitive actions are recorded with an actor, metadata is
redacted, and the entries themselves are immutable.
"""

from __future__ import annotations

from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import build_class, make_admin, make_student
from core.audit import log_event
from core.models import AuditLog


class AuditRecordingTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.admin = make_admin()

    def test_a_successful_login_is_audited(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.profile.user.email, "password": "TelPortal@Test2026"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)

        self.assertEqual(AuditLog.objects.filter(action="auth.login").count(), 1)
        entry = AuditLog.objects.get(action="auth.login")
        self.assertEqual(entry.actor, self.profile.user)
        self.assertEqual(entry.actor_role, "STUDENT")
        self.assertEqual(entry.ip_address, "127.0.0.1")
        # The credential itself is never recorded.
        self.assertNotIn("TelPortal@Test2026", str(entry.metadata))
        self.assertNotIn("password", entry.metadata)

    def test_a_failed_login_is_audited_without_an_actor(self):
        self.client.post(
            "/api/auth/login/",
            {"email": self.profile.user.email, "password": "wrong"},
            format="json",
        )

        entry = AuditLog.objects.get(action="auth.login_failed")
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.metadata["email"], self.profile.user.email)

    def test_publishing_a_result_is_audited(self):
        from common.tests.factories import make_result

        result = make_result(
            student=self.profile,
            subject=self.graph.subject("CS-101"),
            status="DRAFT",
            obtained_marks=35,
        )
        self.as_user(self.admin)
        for target in ("SUBMITTED", "VERIFIED", "PUBLISHED"):
            response = self.client.post(
                f"/api/manage/results/{result.pk}/transition/",
                {"status": target, "note": "Checked against the mark sheet."},
                format="json",
            )
            self.assertEqual(response.status_code, 200, msg=response.content)

        entry = AuditLog.objects.get(action="result.published")
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.actor_role, "ADMIN")
        self.assertEqual(entry.entity_type, "Result")
        self.assertEqual(entry.entity_id, str(result.pk))
        self.assertEqual(entry.summary, f"{result.assessment_name} → Published")
        self.assertEqual(entry.metadata["note"], "Checked against the mark sheet.")
        # Every step of the lifecycle is recorded, each with its own actor.
        self.assertEqual(
            set(
                AuditLog.objects.filter(action__startswith="result.").values_list(
                    "action", flat=True
                )
            ),
            {"result.submitted", "result.verified", "result.published"},
        )
        self.assertTrue(
            AuditLog.objects.filter(action__startswith="result.").exclude(actor=self.admin).count()
            == 0
        )

    def test_submitting_a_practice_attempt_is_audited(self):
        from assessment.models import PracticeAttempt
        from common.tests.factories import add_question, make_paper

        paper = make_paper(self.graph)
        question = add_question(
            paper, order=1, question_type="MCQ", marks=5, correct_option=0
        )
        self.as_user(self.profile.user)
        attempt_id = self.client.post(
            f"/api/papers/{paper.pk}/practice/", {}, format="json"
        ).json()["attempt_id"]

        self.client.post(
            f"/api/practice/{attempt_id}/submit/",
            {"answers": [{"question_id": question.pk, "selected_option": 0}]},
            format="json",
        )

        entry = AuditLog.objects.get(action="practice.submitted")
        self.assertEqual(entry.actor, self.profile.user)
        self.assertEqual(entry.entity_type, "PracticeAttempt")
        # Attempts are addressed by their public UUID, not the sequential pk.
        self.assertEqual(
            entry.entity_id, str(PracticeAttempt.objects.get(pk=attempt_id).public_id)
        )

    def test_staff_can_read_the_audit_trail_but_only_staff(self):
        self.client.post(
            "/api/auth/login/",
            {"email": self.admin.email, "password": "TelPortal@Test2026"},
            format="json",
        )

        response = self.client.get("/api/audit-log/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["action"], "auth.login")
        self.assertEqual(body["results"][0]["actor_role"], "ADMIN")

    def test_the_audit_trail_can_be_filtered_by_action(self):
        self.client.post(
            "/api/auth/login/",
            {"email": self.admin.email, "password": "TelPortal@Test2026"},
            format="json",
        )

        response = self.client.get("/api/audit-log/?action=auth.logout")

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["count"], 0)


class AuditImmutabilityTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.admin = make_admin()
        self.entry = AuditLog.objects.create(
            actor=self.admin,
            actor_role="ADMIN",
            action="result.published",
            entity_type="Result",
            entity_id="1",
            summary="Original summary",
            metadata={"status": "PUBLISHED"},
        )

    def test_an_entry_cannot_be_edited_through_the_orm(self):
        self.entry.summary = "Rewritten history"
        self.entry.metadata = {"status": "REWRITTEN"}

        with self.assertRaises(ValueError) as caught:
            self.entry.save()

        self.assertIn("immutable", str(caught.exception))
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.summary, "Original summary")
        self.assertEqual(self.entry.metadata, {"status": "PUBLISHED"})

    def test_an_entry_cannot_be_deleted_through_the_orm(self):
        with self.assertRaises(ValueError) as caught:
            self.entry.delete()

        self.assertEqual(str(caught.exception), "Audit log entries cannot be deleted.")
        self.assertEqual(AuditLog.objects.filter(pk=self.entry.pk).count(), 1)

    def test_creating_an_entry_still_works(self):
        second = AuditLog.objects.create(
            actor=self.admin, action="auth.login", summary="Signed in"
        )

        self.assertIsNotNone(second.pk)
        self.assertEqual(AuditLog.objects.count(), 2)

    def test_the_audit_trail_exposes_no_mutation_endpoint(self):
        self.as_user(self.admin)

        for method in ("put", "patch", "delete", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    "/api/audit-log/", {"summary": "Rewritten"}, format="json"
                )
                self.assertEqual(response.status_code, 405)

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.summary, "Original summary")
        self.assertEqual(
            AuditLog.objects.filter(summary="Rewritten").count(), 0
        )


class AuditRedactionTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)

    def test_sensitive_metadata_is_redacted(self):
        entry = log_event(
            None,
            action="auth.login",
            user=self.profile.user,
            metadata={
                "email": "student@tel.edu.pk",
                "password": "hunter2",
                "token": "abc.def.ghi",
                "nested": {"refresh": "secret", "keep": 1},
            },
        )

        self.assertEqual(entry.metadata["email"], "student@tel.edu.pk")
        self.assertEqual(entry.metadata["password"], "[redacted]")
        self.assertEqual(entry.metadata["token"], "[redacted]")
        self.assertEqual(entry.metadata["nested"], {"refresh": "[redacted]", "keep": 1})
        self.assertNotIn("hunter2", str(entry.metadata))
        self.assertNotIn("abc.def.ghi", str(entry.metadata))

    def test_actor_role_is_captured_at_the_time_of_the_event(self):
        from accounts.models import Role

        entry = log_event(None, action="result.published", user=self.profile.user)
        self.assertEqual(entry.actor_role, Role.STUDENT)

        self.profile.user.role = Role.CLASS_REPRESENTATIVE
        self.profile.user.save(update_fields=["role"])

        entry.refresh_from_db()
        self.assertEqual(entry.actor_role, Role.STUDENT, "history must not be rewritten")

    def test_an_anonymous_event_is_still_recorded(self):
        entry = log_event(None, action="auth.login_failed", metadata={"email": "x@y.z"})

        self.assertIsNone(entry.actor)
        self.assertEqual(entry.action, "auth.login_failed")
        self.assertEqual(entry.metadata["email"], "x@y.z")
