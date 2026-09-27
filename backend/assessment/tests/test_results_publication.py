"""
Result entry, state machine and student visibility.

A result must stay invisible to the student until TEL publishes it, publishing
must notify exactly once, and the lifecycle must refuse shortcuts.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from assessment import services
from assessment.models import Result, ResultPublication, ResultStatus
from common.exceptions import InvalidWorkflowTransition, TelAPIException
from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import build_class, make_admin, make_student
from core.models import Notification

MANAGE_RESULTS = "/api/manage/results/"


class ResultVisibilityTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.admin = make_admin()
        self.subject = self.graph.subject("CS-101")

    def _create_result(self):
        response = self.as_user(self.admin).post(
            MANAGE_RESULTS,
            {
                "student_id": self.profile.pk,
                "subject_id": self.subject.pk,
                "assessment_name": "Computer Science Weekly Test 01",
                "assessment_type": "WEEKLY_TEST",
                "assessment_date": "2026-02-02",
                "total_marks": 50,
                "obtained_marks": 35,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, msg=response.content)
        return Result.objects.get(pk=response.json()["id"])

    def _transition(self, result, target, note=""):
        response = self.as_user(self.admin).post(
            f"{MANAGE_RESULTS}{result.pk}/transition/",
            {"status": target, "note": note},
            format="json",
        )
        return response

    def _student_results(self):
        response = self.as_user(self.profile.user).get("/api/student/results/")
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def test_a_draft_result_is_invisible_to_the_student(self):
        result = self._create_result()

        self.assertEqual(result.status, ResultStatus.DRAFT)
        body = self._student_results()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["results"], [])

    def test_a_submitted_result_is_invisible_to_the_student(self):
        result = self._create_result()
        response = self._transition(result, "SUBMITTED")

        self.assertEqual(response.status_code, 200, msg=response.content)
        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.SUBMITTED)
        self.assertEqual(self._student_results()["count"], 0)

    def test_a_verified_result_is_invisible_to_the_student(self):
        result = self._create_result()
        self._transition(result, "SUBMITTED")
        response = self._transition(result, "VERIFIED")

        self.assertEqual(response.status_code, 200, msg=response.content)
        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.VERIFIED)
        self.assertEqual(result.verified_by, self.admin)
        self.assertIsNotNone(result.verified_at)
        self.assertEqual(self._student_results()["count"], 0)

    def test_a_published_result_is_visible_and_notifies_exactly_once(self):
        result = self._create_result()
        self._transition(result, "SUBMITTED")
        self._transition(result, "VERIFIED")
        response = self._transition(result, "PUBLISHED")

        self.assertEqual(response.status_code, 200, msg=response.content)
        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.PUBLISHED)
        self.assertEqual(result.published_by, self.admin)
        self.assertIsNotNone(result.published_at)

        body = self._student_results()
        self.assertEqual(body["count"], 1)
        row = body["results"][0]
        self.assertEqual(row["assessment_name"], "Computer Science Weekly Test 01")
        self.assertEqual(row["obtained_marks"], 35.0)
        self.assertEqual(row["total_marks"], 50.0)
        self.assertEqual(row["percentage"], 70.0)
        self.assertEqual(row["grade"], "B")
        self.assertEqual(row["status"], "PUBLISHED")
        self.assertTrue(row["published_at"])

        notifications = Notification.objects.filter(recipient=self.profile.user)
        self.assertEqual(notifications.count(), 1)
        notification = notifications.get()
        self.assertEqual(notification.category, "RESULT")
        self.assertEqual(notification.dedupe_key, f"result-published:{result.pk}")
        self.assertEqual(notification.state, "UNREAD")
        self.assertIn("35 / 50", notification.body)

        # Republishing is impossible, and the notification is not duplicated.
        again = self._transition(result, "PUBLISHED")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 1)

    def test_a_revoked_result_is_hidden_again(self):
        result = self._create_result()
        self._transition(result, "SUBMITTED")
        self._transition(result, "VERIFIED")
        self._transition(result, "PUBLISHED")
        self.assertEqual(self._student_results()["count"], 1)

        Result.objects.filter(pk=result.pk).update(is_revoked=True)

        self.assertEqual(self._student_results()["count"], 0)
        result.refresh_from_db()
        self.assertFalse(result.is_visible_to_students)


class ResultStateMachineTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.admin = make_admin()
        self.subject = self.graph.subject("CS-101")
        self.result = Result.objects.create(
            student=self.profile,
            subject=self.subject,
            assessment_name="Draft assessment",
            assessment_type="WEEKLY_TEST",
            assessment_date=timezone.localdate(),
            total_marks=50,
            obtained_marks=20,
            percentage=40,
            status=ResultStatus.DRAFT,
        )

    def _transition(self, target, note=""):
        return self.as_user(self.admin).post(
            f"{MANAGE_RESULTS}{self.result.pk}/transition/",
            {"status": target, "note": note},
            format="json",
        )

    def test_a_draft_result_cannot_jump_straight_to_published(self):
        response = self._transition("PUBLISHED")

        self.assertEqual(response.status_code, 409, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "invalid_workflow_transition")
        self.assertIn("cannot be moved to", response.json()["error"]["message"])

        self.result.refresh_from_db()
        self.assertEqual(self.result.status, ResultStatus.DRAFT)
        self.assertIsNone(self.result.published_at)
        self.assertFalse(
            ResultPublication.objects.filter(
                result=self.result, to_status=ResultStatus.PUBLISHED
            ).exists()
        )
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 0)

    def test_a_published_result_cannot_be_moved_back(self):
        services.transition_result(result=self.result, target=ResultStatus.SUBMITTED, actor=self.admin)
        services.transition_result(result=self.result, target=ResultStatus.VERIFIED, actor=self.admin)
        services.transition_result(result=self.result, target=ResultStatus.PUBLISHED, actor=self.admin)
        self.assertEqual(
            ResultPublication.objects.filter(result=self.result).count(),
            3,  # submitted, verified, published (the row was created directly)
        )

        for target in ("SUBMITTED", "VERIFIED", "DRAFT"):
            with self.subTest(target=target):
                response = self._transition(target)
                self.assertEqual(response.status_code, 409, msg=response.content)
                self.result.refresh_from_db()
                self.assertEqual(self.result.status, ResultStatus.PUBLISHED)

    def test_an_unknown_target_state_is_refused(self):
        response = self._transition("ARCHIVED")

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.result.refresh_from_db()
        self.assertEqual(self.result.status, ResultStatus.DRAFT)

    def test_every_transition_is_recorded_with_its_actor(self):
        self._transition("SUBMITTED", note="Entered by the office.")
        self._transition("VERIFIED")
        self._transition("PUBLISHED")

        history = list(
            ResultPublication.objects.filter(result=self.result)
            .order_by("id")
            .values_list("from_status", "to_status", "note")
        )
        self.assertEqual(
            history,
            [("DRAFT", "SUBMITTED", "Entered by the office."),
             ("SUBMITTED", "VERIFIED", ""), ("VERIFIED", "PUBLISHED", "")],
        )
        self.assertTrue(
            all(row.actor == self.admin for row in ResultPublication.objects.filter(result=self.result))
        )


class ResultEntryValidationTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.admin = make_admin()
        self.subject = self.graph.subject("CS-101")

    def _payload(self, **overrides):
        payload = {
            "student_id": self.profile.pk,
            "subject_id": self.subject.pk,
            "assessment_name": "Weekly Test 01",
            "assessment_type": "WEEKLY_TEST",
            "assessment_date": "2026-02-02",
            "total_marks": 50,
            "obtained_marks": 35,
        }
        payload.update(overrides)
        return payload

    def test_marks_obtained_greater_than_total_are_rejected(self):
        response = self.as_user(self.admin).post(
            MANAGE_RESULTS, self._payload(obtained_marks=60), format="json"
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertIn("obtained_marks", response.json()["error"]["details"])
        self.assertEqual(Result.objects.count(), 0)

    def test_equal_marks_and_total_are_accepted(self):
        response = self.as_user(self.admin).post(
            MANAGE_RESULTS, self._payload(obtained_marks=50), format="json"
        )

        self.assertEqual(response.status_code, 201, msg=response.content)
        self.assertEqual(response.json()["percentage"], 100.0)
        self.assertEqual(response.json()["grade"], "A+")

    def test_the_service_rejects_impossible_marks_directly(self):
        with self.assertRaises(TelAPIException) as caught:
            services.create_result(
                student=self.profile,
                subject=self.subject,
                paper=None,
                data={
                    "assessment_name": "Weekly Test 01",
                    "assessment_type": "WEEKLY_TEST",
                    "assessment_date": timezone.localdate(),
                    "total_marks": 50,
                    "obtained_marks": 51,
                },
                actor=self.admin,
            )

        self.assertEqual(
            str(caught.exception.detail), "Obtained marks cannot exceed the total marks."
        )
        self.assertEqual(Result.objects.count(), 0)

    def test_the_model_clean_method_rejects_impossible_marks(self):
        result = Result(
            student=self.profile,
            subject=self.subject,
            assessment_name="Weekly Test 01",
            assessment_type="WEEKLY_TEST",
            assessment_date=timezone.localdate(),
            total_marks=50,
            obtained_marks=75,
            percentage=150,
        )

        with self.assertRaises(ValidationError) as caught:
            result.full_clean()

        self.assertIn("obtained_marks", caught.exception.message_dict)

    def test_a_result_derives_its_grade_and_percentage(self):
        result = services.create_result(
            student=self.profile,
            subject=self.subject,
            paper=None,
            data={
                "assessment_name": "Weekly Test 01",
                "assessment_type": "WEEKLY_TEST",
                "assessment_date": timezone.localdate(),
                "total_marks": 40,
                "obtained_marks": 19,
            },
            actor=self.admin,
        )

        self.assertEqual(result.percentage, 47.5)
        self.assertEqual(result.grade, "E")
        self.assertEqual(result.status, ResultStatus.DRAFT)
        self.assertEqual(result.entered_by, self.admin)


class ResultTransitionServiceTests(ServiceTestCase):
    def test_transition_to_an_unknown_state_raises(self):
        graph = build_class()
        profile = make_student(graph, index=1)
        admin = make_admin()
        result = services.create_result(
            student=profile,
            subject=graph.subject("CS-101"),
            paper=None,
            data={
                "assessment_name": "Weekly Test 01",
                "assessment_type": "WEEKLY_TEST",
                "assessment_date": timezone.localdate(),
                "total_marks": 50,
                "obtained_marks": 30,
            },
            actor=admin,
        )

        with self.assertRaises(InvalidWorkflowTransition):
            services.transition_result(result=result, target="DRAFT", actor=admin)
        with self.assertRaises(ValueError):
            # Not a ResultStatus at all.
            services.transition_result(result=result, target="NONSENSE", actor=admin)

        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.DRAFT)
