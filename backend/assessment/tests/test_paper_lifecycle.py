"""
Paper lifecycle: the staff state machine and the class-wide notification that a
publication fans out.
"""

from __future__ import annotations

from assessment import services
from assessment.models import PaperStatus
from common.exceptions import InvalidWorkflowTransition, TelAPIException
from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import add_question, build_class, make_admin, make_paper, make_student
from core.models import Notification, NotificationCategory

MANAGE_PAPERS = "/api/manage/papers/"


class PaperLifecycleTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.admin = make_admin()
        self.paper = make_paper(
            self.graph, status=PaperStatus.DRAFT, exam_type="WEEKLY_TEST", total_marks=10
        )
        add_question(self.paper, order=1, question_type="MCQ", marks=10, correct_option=0)

    def test_the_happy_path_reaches_publication(self):
        for target in ("COMPLETED", "VERIFIED", "PUBLISHED"):
            services.transition_paper(paper=self.paper, target=target, actor=self.admin)
            self.paper.refresh_from_db()
            self.assertEqual(self.paper.status, target)

        self.assertEqual(self.paper.verified_by, self.admin)
        self.assertIsNotNone(self.paper.verified_at)
        self.assertIsNotNone(self.paper.published_at)
        self.assertTrue(self.paper.is_visible_to_students)

    def test_an_illegal_transition_is_refused(self):
        services.transition_paper(paper=self.paper, target="COMPLETED", actor=self.admin)

        with self.assertRaises(InvalidWorkflowTransition):
            services.transition_paper(paper=self.paper, target="PUBLISHED", actor=self.admin)

        self.paper.refresh_from_db()
        self.assertEqual(self.paper.status, PaperStatus.COMPLETED)
        self.assertIsNone(self.paper.published_at)

    def test_practice_cannot_be_opened_on_an_empty_paper(self):
        empty = make_paper(self.graph, title="Empty", status=PaperStatus.PUBLISHED)

        with self.assertRaises(TelAPIException) as caught:
            services.transition_paper(
                paper=empty, target=PaperStatus.PRACTICE_AVAILABLE, actor=self.admin
            )

        self.assertIn("at least one question", str(caught.exception.detail))
        empty.refresh_from_db()
        self.assertEqual(empty.status, PaperStatus.PUBLISHED)

    def test_publication_notifies_every_student_of_the_class_section(self):
        class_students = [make_student(self.graph, index=index) for index in (1, 2)]
        other_graph = build_class(key="B")
        outsider = make_student(other_graph, index=1)
        for target in ("COMPLETED", "VERIFIED", "PUBLISHED"):
            services.transition_paper(paper=self.paper, target=target, actor=self.admin)

        for profile in class_students:
            with self.subTest(student=profile.student_code):
                notification = Notification.objects.get(
                    recipient=profile.user,
                    dedupe_key=f"PAPER:{self.graph.class_room.pk}:{self.graph.section.pk}:"
                    f"paper-{self.paper.pk}-PUBLISHED",
                )
                self.assertEqual(notification.category, NotificationCategory.PAPER)
                self.assertIn(self.paper.title, notification.body)
        self.assertEqual(
            Notification.objects.filter(recipient=outsider.user).count(), 0
        )

    def test_publishing_the_same_paper_twice_is_refused_and_never_duplicates_notifications(self):
        student = make_student(self.graph, index=1)
        for target in ("COMPLETED", "VERIFIED", "PUBLISHED"):
            services.transition_paper(paper=self.paper, target=target, actor=self.admin)
        self.assertEqual(Notification.objects.filter(recipient=student.user).count(), 1)

        with self.assertRaises(InvalidWorkflowTransition):
            services.transition_paper(paper=self.paper, target="PUBLISHED", actor=self.admin)

        self.paper.refresh_from_db()
        self.assertTrue(self.paper.is_visible_to_students)
        self.assertEqual(Notification.objects.filter(recipient=student.user).count(), 1)

    def test_an_archived_paper_disappears_from_the_student_archive(self):
        for target in ("COMPLETED", "VERIFIED", "PUBLISHED"):
            services.transition_paper(paper=self.paper, target=target, actor=self.admin)
        services.transition_paper(paper=self.paper, target="ARCHIVED", actor=self.admin)
        self.paper.refresh_from_db()
        self.assertFalse(self.paper.is_visible_to_students)

        from assessment.models import Paper

        self.assertEqual(
            Paper.objects.visible_to_students().filter(pk=self.paper.pk).count(), 0
        )


class PaperTransitionApiTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.admin = make_admin()
        self.student = make_student(self.graph, index=1)
        self.paper = make_paper(self.graph, status=PaperStatus.DRAFT, total_marks=10)
        add_question(self.paper, order=1, question_type="MCQ", marks=10, correct_option=0)

    def test_the_transition_endpoint_walks_the_lifecycle(self):
        self.as_user(self.admin)

        for target in ("COMPLETED", "VERIFIED", "PUBLISHED"):
            with self.subTest(target=target):
                response = self.client.post(
                    f"{MANAGE_PAPERS}{self.paper.pk}/transition/",
                    {"status": target},
                    format="json",
                )
                self.assertEqual(response.status_code, 200, msg=response.content)
                self.assertEqual(response.json()["status"], target)

        archive = self.as_user(self.student.user).get("/api/student/papers/")
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(
            [row["id"] for row in archive.json()["results"]], [self.paper.pk]
        )

    def test_the_transition_endpoint_refuses_a_shortcut(self):
        self.as_user(self.admin)

        response = self.client.post(
            f"{MANAGE_PAPERS}{self.paper.pk}/transition/",
            {"status": "PUBLISHED"},
            format="json",
        )

        self.assertEqual(response.status_code, 409, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "invalid_workflow_transition")
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.status, PaperStatus.DRAFT)

    def test_the_transition_endpoint_refuses_an_unknown_target(self):
        response = self.as_user(self.admin).post(
            f"{MANAGE_PAPERS}{self.paper.pk}/transition/",
            {"status": "SOMETHING_ELSE"},
            format="json",
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertIn("valid target state", response.json()["error"]["message"])
