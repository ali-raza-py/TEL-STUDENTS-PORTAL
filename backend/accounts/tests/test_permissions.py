"""
Role based access control.

The rules under test:

* a STUDENT is refused by every staff surface;
* a TEACHER may read the review queue and approve, but never publish;
* an ADMIN may publish;
* a CLASS_REPRESENTATIVE gains exactly the timetable-submission capability and
  none of the administrative ones.
"""

from __future__ import annotations

from accounts.models import Role
from accounts.permissions import capabilities_for, has_capability
from academics.models import Timetable, TimetableStatus, TimetableSubmission
from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import (
    build_class,
    make_admin,
    make_entries_payload,
    make_representative,
    make_result,
    make_student,
    make_teacher,
)
from core.models import AuditLog

STAFF_ONLY_ENDPOINTS = [
    ("get", "/api/manage/results/"),
    ("get", "/api/manage/papers/"),
    ("get", "/api/audit-log/"),
    ("post", "/api/manage/announcements/"),
    ("get", "/api/admin/class-representatives/"),
    ("get", "/api/manage/students/"),
]


class StudentIsRefusedByStaffSurfacesTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.student = make_student(self.graph, index=1)

    def test_a_student_gets_403_on_every_staff_endpoint(self):
        self.as_user(self.student.user)

        for method, path in STAFF_ONLY_ENDPOINTS:
            with self.subTest(endpoint=path, method=method):
                if method == "get":
                    response = self.client.get(path)
                else:
                    response = self.client.post(
                        path, {"title": "Sneaky notice", "body": "Should never exist."}, format="json"
                    )

                self.assertEqual(response.status_code, 403, msg=response.content)
                self.assertEqual(response.json()["error"]["code"], "permission_denied")

    def test_a_student_cannot_publish_a_timetable_submission(self):
        admin = make_admin()
        rep_user, _, _ = make_representative(self.graph, index=9)
        submission = self._submit_as_representative(rep_user)

        review = self.as_user(self.student.user).post(
            f"/api/timetable/submissions/{submission.pk}/review/",
            {"decision": "APPROVED", "note": "self approval"},
            format="json",
        )
        self.assertEqual(review.status_code, 403)

        publish = self.as_user(self.student.user).post(
            f"/api/timetable/submissions/{submission.pk}/publish/", {}, format="json"
        )
        self.assertEqual(publish.status_code, 403)
        self.assertEqual(publish.json()["error"]["code"], "permission_denied")

        # The submission is intact, so the 403 above was a permission decision.
        self.as_user(admin)
        self.assertEqual(
            self.client.post(
                f"/api/timetable/submissions/{submission.pk}/review/",
                {"decision": "APPROVED", "note": "ok"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/timetable/submissions/{submission.pk}/publish/", {}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(Timetable.objects.filter(status=TimetableStatus.PUBLISHED).count(), 1)

    def test_a_student_cannot_change_a_result_state(self):
        result = make_result(
            student=self.student,
            subject=self.graph.subject("CS-101"),
            status="DRAFT",
        )

        response = self.as_user(self.student.user).post(
            f"/api/manage/results/{result.pk}/transition/",
            {"status": "PUBLISHED"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        result.refresh_from_db()
        self.assertEqual(result.status, "DRAFT")

    def test_a_student_never_receives_audit_trail_contents(self):
        admin = make_admin()
        self.sign_in(admin)  # writes an "auth.login" audit entry
        self.assertTrue(AuditLog.objects.filter(action="auth.login").exists())

        response = self.as_user(self.student.user).get("/api/audit-log/")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("results", response.json())

    def _submit_as_representative(self, user):
        response = self.as_user(user).post(
            "/api/timetable/submissions/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "summary": "Thursday practical moved to Lab B",
                "entries": make_entries_payload("CS-101", "CS-102"),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, msg=response.content)
        return TimetableSubmission.objects.get(pk=response.json()["id"])


class TeacherReadPublishTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.teacher = make_teacher(campus=self.graph.campus)
        self.admin = make_admin()
        rep_user, _, _ = make_representative(self.graph, index=9)
        response = self.as_user(rep_user).post(
            "/api/timetable/submissions/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "summary": "Thursday practical moved to Lab B",
                "entries": make_entries_payload("CS-101", "CS-102"),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, msg=response.content)
        self.submission = TimetableSubmission.objects.get(pk=response.json()["id"])

    def test_a_teacher_can_read_the_submission_queue(self):
        response = self.as_user(self.teacher).get("/api/timetable/submissions/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["id"], self.submission.pk)
        self.assertEqual(body["results"][0]["status"], "SUBMITTED")
        self.assertEqual(body["results"][0]["entry_count"], 2)
        self.assertEqual(body["results"][0]["submitted_by_name"], self.submission.submitted_by.full_name)

    def test_a_teacher_can_approve_but_cannot_publish(self):
        approved = self.as_user(self.teacher).post(
            f"/api/timetable/submissions/{self.submission.pk}/review/",
            {"decision": "APPROVED", "note": "Approved after review."},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, msg=approved.content)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, "APPROVED")
        self.assertEqual(self.submission.reviewed_by, self.teacher)
        self.assertIsNotNone(self.submission.reviewed_at)

        publish = self.as_user(self.teacher).post(
            f"/api/timetable/submissions/{self.submission.pk}/publish/", {}, format="json"
        )
        self.assertEqual(publish.status_code, 403)
        self.assertEqual(
            publish.json()["error"]["message"], "Only a TEL administrator can publish a timetable."
        )
        self.assertEqual(Timetable.objects.count(), 0)

    def test_an_admin_can_approve_and_publish(self):
        self.as_user(self.admin)

        approve = self.client.post(
            f"/api/timetable/submissions/{self.submission.pk}/review/",
            {"decision": "APPROVED", "note": "Looks right."},
            format="json",
        )
        self.assertEqual(approve.status_code, 200, msg=approve.content)

        publish = self.client.post(
            f"/api/timetable/submissions/{self.submission.pk}/publish/",
            {"change_note": "Published for the new term."},
            format="json",
        )

        self.assertEqual(publish.status_code, 200, msg=publish.content)
        self.assertEqual(publish.json()["status"], "PUBLISHED")
        self.assertEqual(publish.json()["version"], 1)
        self.assertEqual(len(publish.json()["entries"]), 2)
        self.assertEqual(Timetable.objects.get().status, TimetableStatus.PUBLISHED)

    def test_capability_map_separates_teaching_from_publishing(self):
        self.assertTrue(has_capability(self.teacher, "review_timetable_submissions"))
        self.assertTrue(has_capability(self.teacher, "manage_announcements"))
        self.assertFalse(has_capability(self.teacher, "publish_timetable"))
        self.assertFalse(has_capability(self.teacher, "publish_results"))
        self.assertTrue(has_capability(self.admin, "publish_timetable"))
        self.assertTrue(has_capability(self.admin, "publish_results"))


class ClassRepresentativeScopeTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.rep_user, self.rep_profile, self.record = make_representative(
            self.graph, index=9
        )
        self.plain_student = make_student(self.graph, index=2)

    def test_a_representative_gains_the_timetable_capability_only(self):
        response = self.as_user(self.rep_user).get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        capabilities = response.json()["capabilities"]
        self.assertIn("submit_timetable", capabilities)
        self.assertIn("report_timetable_change", capabilities)
        self.assertTrue(set(capabilities_for(Role.STUDENT)).issubset(set(capabilities)))
        for forbidden in (
            "publish_timetable",
            "manage_results",
            "publish_results",
            "manage_papers",
            "view_audit_log",
            "assign_class_representatives",
            "review_requests",
            "manage_attendance",
        ):
            with self.subTest(capability=forbidden):
                self.assertNotIn(forbidden, capabilities)
                self.assertFalse(has_capability(self.rep_user, forbidden))

    def test_a_plain_student_does_not_have_the_timetable_capability(self):
        self.assertFalse(has_capability(self.plain_student.user, "submit_timetable"))
        self.assertIn("submit_timetable", capabilities_for(Role.CLASS_REPRESENTATIVE))

    def test_a_representative_is_refused_by_the_administrative_endpoints(self):
        for method, path in STAFF_ONLY_ENDPOINTS:
            with self.subTest(endpoint=path):
                self.as_user(self.rep_user)
                if method == "get":
                    response = self.client.get(path)
                else:
                    response = self.client.post(
                        path, {"title": "Notice", "body": "Not allowed."}, format="json"
                    )
                self.assertEqual(response.status_code, 403, msg=response.content)

    def test_a_representative_sees_their_own_class_toolkit(self):
        response = self.as_user(self.rep_user).get("/api/class-toolkit/")

        self.assertEqual(response.status_code, 200)
        assignments = response.json()["assignments"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["class_id"], self.graph.class_room.pk)
        self.assertEqual(assignments[0]["section_id"], self.graph.section.pk)
        offered = {row["subject__code"] for row in assignments[0]["subjects"]}
        self.assertEqual(offered, {"CS-101", "CS-102", "CS-103"})

    def test_a_plain_student_gets_an_empty_class_toolkit(self):
        response = self.as_user(self.plain_student.user).get("/api/class-toolkit/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assignments"], [])

    def test_a_representative_can_submit_for_their_own_section(self):
        response = self.as_user(self.rep_user).post(
            "/api/timetable/submissions/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "summary": "Lab B booked for Thursday",
                "entries": make_entries_payload("CS-101"),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, msg=response.content)
        submission = TimetableSubmission.objects.get()
        self.assertEqual(submission.submitted_by, self.rep_user)
        self.assertEqual(submission.status, "SUBMITTED")

    def test_a_representative_cannot_assign_another_representative(self):
        response = self.as_user(self.rep_user).post(
            "/api/admin/class-representatives/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "user_id": self.plain_student.user.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.plain_student.user.refresh_from_db()
        self.assertEqual(self.plain_student.user.role, Role.STUDENT)


class CapabilityUnitTests(ServiceTestCase):
    def test_capabilities_for_an_unknown_role_is_empty(self):
        self.assertEqual(capabilities_for("NOT_A_ROLE"), [])
        self.assertFalse(has_capability(None, "view_dashboard"))
        self.assertFalse(has_capability(self.make_anonymous(), "view_dashboard"))

    def make_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        return AnonymousUser()
