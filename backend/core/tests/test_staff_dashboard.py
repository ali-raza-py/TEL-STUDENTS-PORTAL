"""
Role shaped dashboard tests.

The dashboard is the one endpoint every role lands on, so these cover all three
shapes plus the scoping rules that keep a teacher from seeing another teacher's
classes. A regression here is a blank home screen for a whole role, which is why
each role asserts on the discriminator and on its own key figures.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from accounts.models import Role, StudentProfile
from academics.models import SubjectOffering, TimetableStatus, TimetableSubmission
from academics.selectors import days_until_period, next_period
from assessment.models import PaperStatus, ResultStatus
from common.tests.base import ApiTestCase
from common.tests.factories import (
    add_attendance,
    build_class,
    make_admin,
    make_campus,
    make_paper,
    make_program,
    make_result,
    make_student,
    make_teacher,
    make_timetable,
)
from engagement.models import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    AttendanceStatus,
    Feedback,
    RequestType,
    StudentRequest,
)

DASHBOARD = "/api/dashboard/"
FIRST_SUBJECT = "CS-101"


def make_assignment_for(graph, *, title: str, teacher=None) -> Assignment:
    """An assignment published to the graph's class and section."""

    return Assignment.objects.create(
        title=title,
        subject=graph.subject(FIRST_SUBJECT),
        class_room=graph.class_room,
        section=graph.section,
        teacher=teacher,
        is_published=True,
        due_on=timezone.localdate() + timezone.timedelta(days=7),
    )


def make_submission_for(graph, assignment: Assignment, *, index: int) -> AssignmentSubmission:
    return AssignmentSubmission.objects.create(
        assignment=assignment,
        student=make_student(graph, index=index),
        status=AssignmentStatus.SUBMITTED,
    )


def make_timetable_submission_for(graph, *, index: int) -> TimetableSubmission:
    return TimetableSubmission.objects.create(
        class_room=graph.class_room,
        section=graph.section,
        academic_year=graph.academic_year,
        submitted_by=make_student(graph, index=index).user,
        status=TimetableStatus.SUBMITTED,
        summary="Room swap requested",
    )


class StudentDashboardShapeTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="SD")
        self.student = make_student(self.graph, index=1)

    def test_student_receives_the_student_payload(self):
        self.as_user(self.student.user)
        body = self.client.get(DASHBOARD).json()

        self.assertNotIn("role", body)
        for key in ("identity", "attendance", "performance", "weak_subjects", "timetable"):
            self.assertIn(key, body)
        self.assertEqual(body["identity"]["student_code"], self.student.student_code)

    def test_upcoming_class_serialises_its_countdown(self):
        """A student with a class later today must not 500 building ``starts_in_minutes``."""

        make_timetable(self.graph, subject_codes=(FIRST_SUBJECT,))

        self.as_user(self.student.user)
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200, msg=response.content)

        body = response.json()
        if body.get("next_class") is not None:
            self.assertIsInstance(body["next_class"]["starts_in_minutes"], int)
            self.assertGreaterEqual(body["next_class"]["starts_in_minutes"], 0)

    def test_teacher_does_not_receive_the_student_payload(self):
        self.as_user(make_teacher(email="sd.teacher@tel.edu.pk", employee_code="SD-T1"))
        body = self.client.get(DASHBOARD).json()

        self.assertEqual(body["role"], Role.TEACHER)
        for student_key in ("attendance", "weak_subjects", "timetable", "practice"):
            self.assertNotIn(student_key, body)

    def test_admin_does_not_receive_the_student_payload(self):
        self.as_user(make_admin(email="sd.admin@tel.edu.pk"))
        body = self.client.get(DASHBOARD).json()

        self.assertEqual(body["role"], Role.ADMIN)
        for student_key in ("attendance", "weak_subjects", "timetable", "practice"):
            self.assertNotIn(student_key, body)


class TeacherDashboardTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="TD")
        self.teacher = make_teacher(email="td.teacher@tel.edu.pk", campus=self.graph.campus, employee_code="TD-T1")
        SubjectOffering.objects.filter(
            class_room=self.graph.class_room, section=self.graph.section
        ).update(teacher=self.teacher)
        self.student = make_student(self.graph, index=1)

    def _fetch(self, user=None):
        self.as_user(user or self.teacher)
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def test_shape_and_identity(self):
        body = self._fetch()

        self.assertEqual(body["role"], Role.TEACHER)
        self.assertEqual(body["identity"]["email"], self.teacher.email)
        self.assertEqual(body["identity"]["campus"], self.graph.campus.name)
        for key in ("stats", "teaching", "queues", "today_classes", "at_risk_students"):
            self.assertIn(key, body)

    def test_counts_the_assigned_class_and_its_students(self):
        stats = self._fetch()["stats"]

        self.assertEqual(stats["classes"], 1)
        self.assertEqual(stats["students"], 1)
        self.assertEqual(stats["subjects"], len(self.graph.subjects))

    def test_teaching_load_lists_the_class_with_its_subjects(self):
        rows = self._fetch()["teaching"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class_name"], self.graph.class_room.display_name)
        self.assertEqual(rows[0]["student_count"], 1)
        self.assertEqual(len(rows[0]["subjects"]), len(self.graph.subjects))

    def test_unplaced_teacher_gets_a_hint_not_a_crash(self):
        loner = make_teacher(email="td.loner@tel.edu.pk", employee_code="TD-T2")
        body = self._fetch(user=loner)

        self.assertEqual(body["role"], Role.TEACHER)
        self.assertTrue(body["unplaced_hint"])
        self.assertEqual(body["stats"]["classes"], 0)
        self.assertEqual(body["teaching"], [])

    def test_does_not_leak_another_teachers_classes(self):
        other_graph = build_class(key="TO")
        other = make_teacher(email="td.other@tel.edu.pk", campus=other_graph.campus, employee_code="TD-T3")
        SubjectOffering.objects.filter(
            class_room=other_graph.class_room, section=other_graph.section
        ).update(teacher=other)
        other_student = make_student(other_graph, index=1)

        body = self._fetch()

        self.assertNotIn(other_student.student_code, str(body))
        self.assertEqual(
            [row["class_id"] for row in body["teaching"]], [self.graph.class_room.id]
        )

    def test_counts_unreviewed_submissions_in_own_classes_only(self):
        assignment = make_assignment_for(self.graph, title="Essay")
        make_submission_for(self.graph, assignment, index=2)

        self.assertEqual(self._fetch()["stats"]["unreviewed_submissions"], 1)

        other_graph = build_class(key="TS")
        other_assignment = make_assignment_for(other_graph, title="Elsewhere")
        make_submission_for(other_graph, other_assignment, index=1)

        self.assertEqual(self._fetch()["stats"]["unreviewed_submissions"], 1)

    def test_surfaces_open_timetable_submissions(self):
        make_timetable_submission_for(self.graph, index=3)

        rows = self._fetch()["queues"]["timetable_submissions"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class_name"], self.graph.class_room.display_name)

    def test_next_class_wraps_to_next_week_at_the_weekend(self):
        """The dashboard must still offer a next class on a day with no periods."""

        from academics.models import Timetable, TimetableEntry

        timetable = Timetable.objects.create(
            class_room=self.graph.class_room,
            section=self.graph.section,
            academic_year=self.graph.academic_year,
            version=1,
            status=TimetableStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        # Monday-Friday only, exactly like a real published timetable.
        for weekday in range(5):
            TimetableEntry.objects.create(
                timetable=timetable,
                day_of_week=weekday,
                start_time=time(8, 0),
                end_time=time(8, 45),
                subject=self.graph.subject(FIRST_SUBJECT),
                teacher=self.teacher,
            )

        body = self._fetch()

        if timezone.localtime().weekday() in range(5):
            self.assertTrue(body["next_class"] is not None or body["today_classes"])
        else:
            # Weekend: nothing today, but the wrap must still find Monday.
            self.assertEqual(body["today_classes"], [])
            self.assertIsNotNone(body["next_class"], msg="next class must wrap to next week")
            self.assertFalse(body["next_class"]["is_today"])

    def test_flags_low_attendance_as_at_risk(self):
        for offset in range(1, 5):
            add_attendance(
                student=self.student,
                subject=self.graph.subject(FIRST_SUBJECT),
                class_room=self.graph.class_room,
                status=AttendanceStatus.ABSENT,
                days_ago=offset,
            )

        at_risk = self._fetch()["at_risk_students"]

        self.assertEqual(len(at_risk), 1)
        self.assertEqual(at_risk[0]["student_code"], self.student.student_code)
        self.assertEqual(at_risk[0]["percentage"], 0.0)
        self.assertEqual(at_risk[0]["sessions"], 4)

    def test_good_attendance_is_not_flagged(self):
        add_attendance(
            student=self.student,
            subject=self.graph.subject(FIRST_SUBJECT),
            class_room=self.graph.class_room,
            status=AttendanceStatus.PRESENT,
            days_ago=1,
        )

        self.assertEqual(self._fetch()["at_risk_students"], [])


class AdminDashboardTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class(key="AD")
        self.admin = make_admin(email="ad.admin@tel.edu.pk")

    def _fetch(self):
        self.as_user(self.admin)
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def test_shape_and_headline_counts(self):
        make_student(self.graph, index=1)
        make_student(self.graph, index=2)
        make_teacher(email="ad.teacher@tel.edu.pk", campus=self.graph.campus, employee_code="AD-T1")

        body = self._fetch()

        self.assertEqual(body["role"], Role.ADMIN)
        self.assertEqual(body["stats"]["students"], 2)
        self.assertEqual(body["stats"]["teachers"], 1)
        self.assertEqual(body["stats"]["classes"], 1)
        self.assertEqual(body["stats"]["unplaced_students"], 0)
        for key in ("enrolment", "queues", "upcoming_events", "recent_activity", "academic_year"):
            self.assertIn(key, body)

    def test_reports_the_current_academic_year(self):
        body = self._fetch()

        self.assertTrue(body["academic_year"]["is_current"])
        self.assertEqual(body["academic_year"]["label"], self.graph.academic_year.label)

    def test_breaks_enrolment_down_by_campus_and_programme(self):
        make_student(self.graph, index=1)

        enrolment = self._fetch()["enrolment"]

        self.assertEqual(enrolment["by_campus"][0]["name"], self.graph.campus.name)
        self.assertEqual(enrolment["by_campus"][0]["total"], 1)
        self.assertEqual(enrolment["by_program"][0]["name"], self.graph.program.name)

    def test_counts_papers_awaiting_verification(self):
        make_paper(self.graph, status=PaperStatus.COMPLETED, title="Pending check")
        make_paper(self.graph, status=PaperStatus.DRAFT, title="Still writing")

        body = self._fetch()

        self.assertEqual(body["stats"]["papers_unverified"], 1)
        self.assertEqual(body["stats"]["papers_draft"], 1)
        self.assertEqual(len(body["queues"]["papers_awaiting_verification"]), 1)
        self.assertEqual(
            body["queues"]["papers_awaiting_verification"][0]["title"], "Pending check"
        )

    def test_counts_results_awaiting_publication(self):
        make_result(
            student=make_student(self.graph, index=1),
            subject=self.graph.subject(FIRST_SUBJECT),
            status=ResultStatus.VERIFIED,
        )

        body = self._fetch()

        self.assertEqual(body["stats"]["results_unpublished"], 1)
        self.assertEqual(len(body["queues"]["results_awaiting_publication"]), 1)

    def test_lists_students_missing_a_placement(self):
        from accounts.models import User

        orphan_user = User.objects.create_user(
            email="ad.orphan@student.tel.edu.pk",
            password="x",
            full_name="Unplaced Student",
            role=Role.STUDENT,
        )
        profile = StudentProfile.objects.create(
            user=orphan_user,
            student_code="TEL-ORPHAN-001",
            campus=make_campus(),
            program=make_program(),
        )

        body = self._fetch()

        self.assertEqual(body["stats"]["unplaced_students"], 1)
        row = body["queues"]["unplaced_students"][0]
        self.assertEqual(row["student_code"], profile.student_code)
        for missing in ("class", "section", "academic year"):
            self.assertIn(missing, row["missing"])

    def test_counts_open_requests_and_new_feedback(self):
        student = make_student(self.graph, index=1)
        StudentRequest.objects.create(
            student=student,
            request_type=RequestType.LEAVE,
            subject_line="Medical leave",
        )
        Feedback.objects.create(student=student, category="PORTAL", message="Login failed")

        body = self._fetch()

        self.assertEqual(body["stats"]["open_requests"], 1)
        self.assertEqual(body["stats"]["new_feedback"], 1)
        self.assertTrue(body["queues"]["open_requests"][0]["ticket_id"].startswith("TEL-"))

    def test_no_teachers_means_a_zero_not_an_error(self):
        body = self._fetch()

        self.assertEqual(body["stats"]["teachers"], 0)
        self.assertEqual(body["stats"]["new_feedback"], 0)
        self.assertEqual(body["queues"]["unplaced_students"], [])
        self.assertEqual(body["enrolment"]["by_campus"], [])


class EmptyAdminDashboardTests(ApiTestCase):
    """A fresh institution has no rows at all — every figure must still be present."""

    def test_empty_institution_returns_zeroes_not_missing_keys(self):
        self.as_user(make_admin(email="empty.admin@tel.edu.pk"))
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()

        self.assertEqual(body["role"], Role.ADMIN)
        for key in (
            "students",
            "teachers",
            "classes",
            "programs",
            "unplaced_students",
            "papers_draft",
            "papers_unverified",
            "results_unpublished",
            "timetable_queue",
            "open_requests",
            "new_feedback",
        ):
            self.assertEqual(body["stats"][key], 0, msg=key)
        for key, value in body["queues"].items():
            self.assertEqual(value, [], msg=key)
        self.assertEqual(body["enrolment"]["by_campus"], [])
        self.assertEqual(body["enrolment"]["by_program"], [])
        self.assertEqual(body["upcoming_events"], [])
        self.assertEqual(body["recent_activity"], [])
        self.assertFalse(body["academic_year"]["is_current"])


class DashboardAccessTests(ApiTestCase):
    def test_anonymous_caller_is_rejected(self):
        self.assertEqual(self.client.get(DASHBOARD).status_code, 401)


class NextPeriodTests(SimpleTestCase):
    """The weekly wrap-around, pinned deterministically rather than by today's date."""

    def _entry(self, day_of_week: int):
        return SimpleNamespace(day_of_week=day_of_week, end_time=time(9, 0))

    def _at(self, weekday: int, hour: int):
        """A datetime falling on ``weekday`` (Monday=0) in a known week."""

        sunday = datetime(2026, 9, 27, hour, tzinfo=timezone.get_current_timezone())
        if sunday.weekday() != 6:
            raise AssertionError("2026-09-27 must be a Sunday for this fixture to hold")
        return sunday + timedelta(days=(weekday - 6) % 7)

    def test_finds_a_later_day_in_the_same_week(self):
        # A Wednesday at 12:00 looking at a Mon-Fri timetable whose periods all
        # ended at 09:00: today's period is over, so the next one is Thursday's.
        entries = [self._entry(day) for day in range(5)]
        found = next_period(entries, self._at(2, 12))

        self.assertEqual(found.day_of_week, 3)

    def test_finds_a_later_period_today(self):
        entries = [self._entry(2)]
        # Wednesday at 07:00, before the 09:00 end time.
        found = next_period(entries, self._at(2, 7))

        self.assertEqual(found.day_of_week, 2)

    def test_wraps_to_next_week_on_a_sunday(self):
        entries = [self._entry(day) for day in range(5)]
        # Sunday is weekday 6, so nothing is later this week.
        found = next_period(entries, self._at(6, 12))

        self.assertEqual(found.day_of_week, 0)

    def test_returns_none_for_an_empty_timetable(self):
        self.assertIsNone(next_period([], self._at(6, 12)))

    def test_returns_the_first_period_when_the_week_has_elapsed(self):
        entries = [self._entry(day) for day in range(5)]
        # Friday evening: the week is over, so Monday is next.
        found = next_period(entries, self._at(4, 20))

        self.assertEqual(found.day_of_week, 0)

    def test_days_until_counts_forward_around_the_week(self):
        self.assertEqual(days_until_period(self._entry(0), self._at(6, 12)), 1)
        self.assertEqual(days_until_period(self._entry(4), self._at(2, 12)), 2)
        self.assertEqual(days_until_period(self._entry(2), self._at(2, 12)), 0)
