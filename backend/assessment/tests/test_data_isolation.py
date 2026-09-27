"""
Data isolation between students.

Every assertion here expects **404, never 403**: a 403 would confirm that the
record exists, which is itself an information leak. Each test also proves the
record really is reachable by its owner, so a 404 can never pass vacuously.
"""

from __future__ import annotations

from assessment.models import PaperStatus, PracticeAttempt
from common.tests.base import ApiTestCase
from common.tests.factories import (
    add_question,
    build_class,
    make_paper,
    make_result,
    make_student,
)
from core.models import Notification


class PracticeAttemptIsolationTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.other_graph = build_class(key="B")
        self.student_a = make_student(self.graph, index=1)
        self.student_b = make_student(self.graph, index=2)
        self.paper = make_paper(self.graph, status=PaperStatus.PRACTICE_AVAILABLE)
        self.question = add_question(
            self.paper, order=1, question_type="MCQ", marks=10, correct_option=1
        )
        self.attempt_b, self.attempt_b_id = self._begin(self.student_b)

    def _begin(self, profile):
        response = self.as_user(profile.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        attempt_id = response.json()["attempt_id"]
        self.as_user(profile.user).post(
            f"/api/practice/{attempt_id}/save/",
            {"answers": [{"question_id": self.question.pk, "selected_option": 1}]},
            format="json",
        )
        return PracticeAttempt.objects.get(pk=attempt_id), attempt_id

    def _assert_not_found(self, response):
        self.assertEqual(response.status_code, 404, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "not_found")
        # 403 would confirm the record exists.
        self.assertNotEqual(response.status_code, 403)

    def test_a_student_cannot_read_another_students_in_progress_attempt(self):
        # The owner is refused for a different reason (not submitted yet), so the
        # 404 below is about ownership and not about missing data.
        owner = self.as_user(self.student_b.user).get(
            f"/api/practice/{self.attempt_b_id}/review/"
        )
        self.assertEqual(owner.status_code, 400)
        self.assertIn("Submit the attempt", owner.json()["error"]["message"])

        response = self.as_user(self.student_a.user).get(
            f"/api/practice/{self.attempt_b_id}/review/"
        )

        self._assert_not_found(response)

    def test_a_student_cannot_submit_another_students_attempt(self):
        response = self.as_user(self.student_a.user).post(
            f"/api/practice/{self.attempt_b_id}/submit/", {}, format="json"
        )

        self._assert_not_found(response)
        self.attempt_b.refresh_from_db()
        self.assertEqual(self.attempt_b.status, "IN_PROGRESS")
        self.assertIsNone(self.attempt_b.submitted_at)
        self.assertEqual(self.attempt_b.correct_count, 0)
        self.assertEqual(self.attempt_b.answers.get().is_correct, None)

    def test_a_student_cannot_write_to_another_students_attempt(self):
        other_question = add_question(
            self.paper, order=2, question_type="MCQ", marks=1, correct_option=0
        )

        response = self.as_user(self.student_a.user).post(
            f"/api/practice/{self.attempt_b_id}/save/",
            {"answers": [{"question_id": other_question.pk, "selected_option": 0}]},
            format="json",
        )

        self._assert_not_found(response)
        answers = self.attempt_b.answers.all()
        self.assertEqual([row.question_id for row in answers], [self.question.pk])

    def test_a_student_cannot_read_another_students_review_with_the_answer_key(self):
        self.as_user(self.student_b.user).post(
            f"/api/practice/{self.attempt_b_id}/submit/", {}, format="json"
        )
        owner = self.as_user(self.student_b.user).get(
            f"/api/practice/{self.attempt_b_id}/review/"
        )
        self.assertEqual(owner.status_code, 200, msg=owner.content)
        self.assertEqual(owner.json()["review"][0]["correct_option"], 1)

        response = self.as_user(self.student_a.user).get(
            f"/api/practice/{self.attempt_b_id}/review/"
        )

        self._assert_not_found(response)
        self.assertNotIn("correct_option", response.content.decode())

    def test_practice_history_only_lists_the_students_own_attempts(self):
        own_id = self.as_user(self.student_a.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        ).json()["attempt_id"]

        body = self.as_user(self.student_a.user).get(
            "/api/student/practice-history/"
        ).json()

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["attempt_id"], own_id)
        self.assertNotIn(self.attempt_b_id, [row["attempt_id"] for row in body["results"]])


class PaperIsolationTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.other_graph = build_class(key="B")
        self.student = make_student(self.graph, index=1)
        self.foreign_paper = make_paper(
            self.other_graph, status=PaperStatus.PRACTICE_AVAILABLE
        )
        add_question(self.foreign_paper, order=1, question_type="MCQ", marks=5, correct_option=0)
        self.own_paper = make_paper(
            self.graph, title="My class paper", status=PaperStatus.PRACTICE_AVAILABLE
        )
        add_question(self.own_paper, order=1, question_type="MCQ", marks=5, correct_option=0)

    def test_a_student_cannot_read_a_paper_belonging_to_another_class(self):
        response = self.as_user(self.student.user).get(f"/api/papers/{self.foreign_paper.pk}/")

        self.assertEqual(response.status_code, 404, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "not_found")
        self.assertNotIn(self.foreign_paper.title, response.content.decode())

        # Their own class's paper is readable, so the 404 is a class-scope rule.
        own = self.as_user(self.student.user).get(f"/api/papers/{self.own_paper.pk}/")
        self.assertEqual(own.status_code, 200, msg=own.content)
        self.assertEqual(own.json()["title"], "My class paper")

    def test_a_student_cannot_start_practice_on_another_classs_paper(self):
        response = self.as_user(self.student.user).post(
            f"/api/papers/{self.foreign_paper.pk}/practice/", {}, format="json"
        )

        self.assertEqual(response.status_code, 404, msg=response.content)
        self.assertEqual(
            PracticeAttempt.objects.filter(paper=self.foreign_paper).count(), 0
        )

    def test_the_paper_archive_only_lists_the_students_own_class(self):
        response = self.as_user(self.student.user).get("/api/student/papers/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["id"], self.own_paper.pk)
        self.assertNotIn(
            self.foreign_paper.pk, [row["id"] for row in body["results"]]
        )


class ResultIsolationTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.student_a = make_student(self.graph, index=1)
        self.student_b = make_student(self.graph, index=2)
        self.subject = self.graph.subject("CS-101")
        self.result_a = make_result(student=self.student_a, subject=self.subject)
        self.result_b = make_result(
            student=self.student_b,
            subject=self.subject,
            assessment_name="Student B assessment",
        )

    def test_a_student_cannot_read_another_students_results(self):
        response = self.as_user(self.student_a.user).get("/api/student/results/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["assessment_name"], "Computer Science assessment")
        self.assertNotIn("Student B assessment", response.content.decode())

    def test_filtering_by_subject_cannot_widen_the_result_set(self):
        response = self.as_user(
            self.student_a.user
        ).get(f"/api/student/results/?subject={self.subject.pk}")

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["count"], 1)

    def test_each_student_only_sees_their_own_published_result(self):
        body_a = self.as_user(self.student_a.user).get("/api/student/results/").json()
        body_b = self.as_user(self.student_b.user).get("/api/student/results/").json()

        self.assertEqual([row["assessment_name"] for row in body_a["results"]],
                         ["Computer Science assessment"])
        self.assertEqual([row["assessment_name"] for row in body_b["results"]],
                         ["Student B assessment"])

    def test_analytics_never_mix_two_students_results(self):
        make_result(
            student=self.student_a,
            subject=self.subject,
            obtained_marks=10,
            assessment_name="Student A weak test",
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.student_a.user).count(), 0
        )

        body = self.as_user(self.student_b.user).get("/api/student/analytics/").json()

        self.assertTrue(body["has_results"])
        performance = body["subjects"][0]
        self.assertEqual(performance["assessments"], 1)
        self.assertEqual(performance["latest_assessment"], "Student B assessment")
        # Student B's single assessment is above the threshold, so nothing flagged.
        self.assertEqual(body["weak_subjects"], [])
