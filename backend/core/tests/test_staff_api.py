"""
Staff register API contract tests.

The staff pages are thin, so most of their behaviour lives in the API. These pin
the parts the pages depend on: that a result row identifies its student, that the
register filters are real server-side filters, and that the audit log is
paginated, searchable, and read only.
"""

from __future__ import annotations

from accounts.models import Role
from academics.models import TimetableStatus
from assessment.models import PaperStatus, ResultStatus
from common.tests.base import ApiTestCase
from common.tests.factories import (
    build_class,
    make_admin,
    make_paper,
    make_result,
    make_student,
    make_teacher,
)
from core.models import AuditLog

FIRST_SUBJECT = "CS-101"
SECOND_SUBJECT = "CS-102"


class ResultRegisterTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="RR")
        self.admin = make_admin(email="rr.admin@tel.edu.pk")
        self.student = make_student(self.graph, index=1, full_name="Result Student")
        self.subject = self.graph.subject(FIRST_SUBJECT)

    def _result(self, **kwargs):
        return make_result(
            student=kwargs.pop("student", self.student),
            subject=kwargs.pop("subject", self.subject),
            **kwargs,
        )

    def _register(self, query: str = ""):
        self.as_user(self.admin)
        response = self.client.get(f"/api/manage/results/{query}")
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def test_every_row_identifies_its_student(self):
        """A result row that cannot be attributed to a student is not a record."""

        self._result()

        rows = self._register()["results"]

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["student"], self.student.pk)
        self.assertEqual(row["student_name"], "Result Student")
        self.assertEqual(row["student_code"], self.student.student_code)
        self.assertEqual(row["class_name"], self.graph.class_room.display_name)
        self.assertEqual(row["section_name"], self.graph.section.name)

    def test_filters_by_status(self):
        self._result(status=ResultStatus.VERIFIED)
        self._result(status=ResultStatus.PUBLISHED)

        rows = self._register(f"?status={ResultStatus.VERIFIED}")["results"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], ResultStatus.VERIFIED)

    def test_filters_by_subject(self):
        self._result(subject=self.subject)
        self._result(subject=self.graph.subject(SECOND_SUBJECT))

        rows = self._register(f"?subject={self.subject.pk}")["results"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], self.subject.pk)

    def test_filters_by_subject_code(self):
        self._result(subject=self.graph.subject(SECOND_SUBJECT))

        rows = self._register(f"?subject={SECOND_SUBJECT}")["results"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_code"], SECOND_SUBJECT)

    def test_searches_by_student_name(self):
        self._result()

        self.assertEqual(len(self._register("?search=Result+Student")["results"]), 1)
        self.assertEqual(len(self._register("?search=Nobody+Here")["results"]), 0)

    def test_searches_by_assessment_name(self):
        self._result(assessment_name="Midterm Paper")

        self.assertEqual(len(self._register("?search=Midterm")["results"]), 1)

    def test_count_reflects_the_filter_not_the_page(self):
        for index in range(3):
            self._result(student=make_student(self.graph, index=index + 2))

        payload = self._register("?limit=2")

        self.assertEqual(payload["count"], 3)
        self.assertEqual(len(payload["results"]), 2)

    def test_limit_is_capped(self):
        body = self._register("?limit=9999")

        self.assertLessEqual(len(body["results"]), 200)

    def test_students_cannot_reach_the_register(self):
        self.as_user(self.student.user)
        response = self.client.get("/api/manage/results/")

        self.assertEqual(response.status_code, 403)


class PaperRegisterTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="PR")
        self.admin = make_admin(email="pr.admin@tel.edu.pk")

    def test_paper_register_lists_the_full_lifecycle(self):
        make_paper(self.graph, status=PaperStatus.DRAFT, title="Draft one")
        make_paper(self.graph, status=PaperStatus.PUBLISHED, title="Live one")

        self.as_user(self.admin)
        body = self.client.get("/api/manage/papers/").json()

        titles = {row["title"] for row in body["results"]}
        self.assertEqual(titles, {"Draft one", "Live one"})
        self.assertEqual(body["count"], 2)

    def test_filters_by_status(self):
        make_paper(self.graph, status=PaperStatus.DRAFT, title="Draft one")
        make_paper(self.graph, status=PaperStatus.VERIFIED, title="Checked one")

        self.as_user(self.admin)
        body = self.client.get(f"/api/manage/papers/?status={PaperStatus.VERIFIED}").json()

        self.assertEqual([row["title"] for row in body["results"]], ["Checked one"])

    def test_students_are_told_to_use_the_archive(self):
        student = make_student(self.graph, index=1)
        self.as_user(student.user)
        response = self.client.get("/api/manage/papers/")

        self.assertEqual(response.status_code, 403)


class AuditLogTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="AL")
        self.admin = make_admin(email="al.admin@tel.edu.pk")
        self.teacher = make_teacher(
            email="al.teacher@tel.edu.pk", campus=self.graph.campus, employee_code="AL-T1"
        )
        self.student = make_student(self.graph, index=1)

    def test_read_only(self):
        self.as_user(self.admin)
        response = self.client.post("/api/audit-log/", {"action": "forged"}, format="json")

        self.assertEqual(response.status_code, 405)

    def test_paginates_newest_first(self):
        for index in range(5):
            AuditLog.objects.create(
                actor=self.admin, action="paper.created", summary=f"Paper {index}"
            )

        self.as_user(self.admin)
        body = self.client.get("/api/audit-log/?page_size=2").json()

        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 2)
        self.assertEqual(body["count"], 5)
        self.assertTrue(body["has_next"])
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["summary"], "Paper 4")

    def test_searches_action_and_summary(self):
        AuditLog.objects.create(actor=self.admin, action="paper.created", summary="Algebra paper")
        AuditLog.objects.create(actor=self.admin, action="event.created", summary="Holiday")

        self.as_user(self.admin)

        self.assertEqual(len(self.client.get("/api/audit-log/?search=Algebra").json()["results"]), 1)
        self.assertEqual(len(self.client.get("/api/audit-log/?search=event").json()["results"]), 1)

    def test_filters_by_actor_role(self):
        AuditLog.objects.create(actor=self.admin, action="paper.created", actor_role=Role.ADMIN)
        AuditLog.objects.create(actor=self.teacher, action="paper.created", actor_role=Role.TEACHER)

        self.as_user(self.admin)
        body = self.client.get(f"/api/audit-log/?role={Role.TEACHER}").json()

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["actor_role"], Role.TEACHER)

    def test_teacher_may_read_but_student_may_not(self):
        self.as_user(self.teacher)
        self.assertEqual(self.client.get("/api/audit-log/").status_code, 200)

        self.as_user(self.student.user)
        self.assertEqual(self.client.get("/api/audit-log/").status_code, 403)


class TimetableReviewTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="TR")
        self.teacher = make_teacher(
            email="tr.teacher@tel.edu.pk", campus=self.graph.campus, employee_code="TR-T1"
        )
        self.admin = make_admin(email="tr.admin@tel.edu.pk")
        self.submitter = make_student(self.graph, index=1)

    def _submission(self):
        from academics.models import TimetableSubmission

        return TimetableSubmission.objects.create(
            class_room=self.graph.class_room,
            section=self.graph.section,
            academic_year=self.graph.academic_year,
            submitted_by=self.submitter.user,
            status=TimetableStatus.SUBMITTED,
            summary="Room change",
        )

    def test_teacher_can_approve(self):
        submission = self._submission()
        self.as_user(self.teacher)
        response = self.client.post(
            f"/api/timetable/submissions/{submission.pk}/review/",
            {"decision": TimetableStatus.APPROVED, "note": "Fine"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["status"], TimetableStatus.APPROVED)

    def test_teacher_cannot_publish(self):
        """Approval and publication are separate powers."""

        submission = self._submission()
        self.as_user(self.teacher)
        self.client.post(
            f"/api/timetable/submissions/{submission.pk}/review/",
            {"decision": TimetableStatus.APPROVED, "note": "Fine"},
            format="json",
        )
        response = self.client.post(
            f"/api/timetable/submissions/{submission.pk}/publish/", {}, format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_publishing_requires_approval_first(self):
        submission = self._submission()
        self.as_user(self.admin)
        response = self.client.post(
            f"/api/timetable/submissions/{submission.pk}/publish/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_rejection_requires_a_note(self):
        submission = self._submission()
        self.as_user(self.teacher)
        response = self.client.post(
            f"/api/timetable/submissions/{submission.pk}/review/",
            {"decision": TimetableStatus.REJECTED},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_students_cannot_review(self):
        submission = self._submission()
        self.as_user(self.submitter.user)
        response = self.client.post(
            f"/api/timetable/submissions/{submission.pk}/review/",
            {"decision": TimetableStatus.APPROVED},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class StaffNavigationCapabilityTests(ApiTestCase):
    """The staff pages are gated by these capabilities, so they are pinned here."""

    def test_teacher_receives_the_staff_capabilities_it_needs(self):
        teacher = make_teacher(
            email="nav.teacher@tel.edu.pk", campus=None, employee_code="NAV-T1"
        )
        self.as_user(teacher)
        me = self.client.get("/api/auth/me/").json()

        capabilities = set(me["capabilities"])
        for required in (
            "view_students",
            "review_timetable_submissions",
            "review_requests",
            "manage_announcements",
            "manage_academic_events",
            "view_audit_log",
        ):
            self.assertIn(required, capabilities)

        self.assertNotIn("manage_papers", capabilities)
        self.assertNotIn("manage_results", capabilities)
        self.assertNotIn("publish_timetable", capabilities)

    def test_students_receive_no_staff_capabilities(self):
        graph = build_class(key="NV")
        student = make_student(graph, index=1)
        self.as_user(student.user)
        me = self.client.get("/api/auth/me/").json()

        staff = {
            "view_students",
            "review_timetable_submissions",
            "publish_timetable",
            "manage_papers",
            "manage_results",
            "manage_announcements",
            "manage_academic_events",
            "review_requests",
            "view_audit_log",
        }
        self.assertEqual(staff & set(me["capabilities"]), set())
