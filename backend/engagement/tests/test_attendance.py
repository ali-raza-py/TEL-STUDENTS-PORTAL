"""
Attendance summary.

The summary must say so explicitly when there is no data, count present / late /
excused as attended, and rank subjects worst first.
"""

from __future__ import annotations

from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import add_attendance, build_class, make_student
from engagement.models import AttendanceStatus
from engagement.selectors import attendance_summary

ALL_LABELS_ZERO = {"Present": 0, "Absent": 0, "Late": 0, "Excused": 0, "On duty": 0}


class AttendanceSummaryTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.computer_science = self.graph.subject("CS-101")
        self.maths = self.graph.subject("CS-102")
        self.physics = self.graph.subject("CS-103")

    def _record(self, subject, status, *, days_ago=0):
        return add_attendance(
            student=self.profile,
            subject=subject,
            class_room=self.graph.class_room,
            status=status,
            days_ago=days_ago,
        )

    def test_the_summary_is_unavailable_when_no_records_exist(self):
        summary = attendance_summary(self.profile)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["message"], "No attendance data available yet.")
        self.assertIsNone(summary["overall_percentage"])
        self.assertEqual(summary["subjects"], [])
        self.assertEqual(summary["counts"], ALL_LABELS_ZERO)
        self.assertEqual(summary["recent"], [])
        self.assertEqual(summary["monthly_trend"], [])
        # There is deliberately no "lowest subject" while nothing is recorded.
        self.assertIsNone(summary.get("lowest_subject"))
        self.assertNotIn("total_classes", summary)

    def test_present_late_and_excused_count_as_attended_and_absent_does_not(self):
        for offset, status in enumerate(
            [
                AttendanceStatus.PRESENT,
                AttendanceStatus.PRESENT,
                AttendanceStatus.LATE,
                AttendanceStatus.EXCUSED,
                AttendanceStatus.ABSENT,
            ]
        ):
            self._record(self.computer_science, status, days_ago=offset)

        summary = attendance_summary(self.profile)

        self.assertTrue(summary["available"])
        self.assertEqual(summary["attended_classes"], 4)
        self.assertEqual(summary["total_classes"], 5)
        self.assertEqual(summary["overall_percentage"], 80.0)
        self.assertEqual(
            summary["counts"],
            {"Present": 2, "Absent": 1, "Late": 1, "Excused": 1, "On duty": 0},
        )

        row = summary["subjects"][0]
        self.assertEqual(row["subject_code"], "CS-101")
        self.assertEqual(row["present"], 2)
        self.assertEqual(row["absent"], 1)
        self.assertEqual(row["late"], 1)
        self.assertEqual(row["excused"], 1)
        self.assertEqual(row["on_duty"], 0)
        self.assertEqual(row["total_classes"], 5)
        self.assertEqual(row["percentage"], 80.0)
        self.assertEqual(summary["lowest_subject"]["subject_code"], "CS-101")

    def test_absent_only_records_give_zero_percent(self):
        for offset in range(3):
            self._record(self.maths, AttendanceStatus.ABSENT, days_ago=offset)

        summary = attendance_summary(self.profile)

        self.assertTrue(summary["available"])
        self.assertEqual(summary["attended_classes"], 0)
        self.assertEqual(summary["total_classes"], 3)
        self.assertEqual(summary["overall_percentage"], 0.0)
        self.assertEqual(summary["subjects"][0]["percentage"], 0.0)
        self.assertEqual(summary["subjects"][0]["absent"], 3)

    def test_on_duty_counts_as_attended(self):
        self._record(self.maths, AttendanceStatus.ON_DUTY, days_ago=0)
        self._record(self.maths, AttendanceStatus.ABSENT, days_ago=1)

        summary = attendance_summary(self.profile)

        self.assertEqual(summary["attended_classes"], 1)
        self.assertEqual(summary["overall_percentage"], 50.0)
        self.assertEqual(summary["counts"]["On duty"], 1)
        self.assertEqual(summary["subjects"][0]["on_duty"], 1)

    def test_subject_rows_are_sorted_worst_first(self):
        # One record per subject per day, so spread them over distinct dates.
        for offset, status in enumerate([AttendanceStatus.PRESENT]):
            self._record(self.computer_science, status, days_ago=offset)  # 100%
        for offset, status in enumerate([AttendanceStatus.PRESENT, AttendanceStatus.ABSENT]):
            self._record(self.physics, status, days_ago=offset)  # 50%
        for offset, status in enumerate(
            [AttendanceStatus.ABSENT, AttendanceStatus.ABSENT, AttendanceStatus.ABSENT,
             AttendanceStatus.PRESENT]
        ):
            self._record(self.maths, status, days_ago=offset)  # 25%

        summary = attendance_summary(self.profile)

        order = [row["subject_code"] for row in summary["subjects"]]
        self.assertEqual(order, ["CS-102", "CS-103", "CS-101"])
        percentages = [row["percentage"] for row in summary["subjects"]]
        self.assertEqual(percentages, [25.0, 50.0, 100.0])
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(summary["lowest_subject"]["subject_code"], "CS-102")
        # Overall is a flat record count, not the mean of the subject rates.
        self.assertEqual(summary["attended_classes"], 3)
        self.assertEqual(summary["total_classes"], 7)
        self.assertEqual(summary["overall_percentage"], 42.9)

    def test_the_recent_feed_and_monthly_trend_are_populated(self):
        self._record(self.maths, AttendanceStatus.PRESENT, days_ago=0)
        self._record(self.maths, AttendanceStatus.ABSENT, days_ago=40)

        summary = attendance_summary(self.profile)

        self.assertEqual(len(summary["recent"]), 2)
        self.assertEqual(summary["recent"][0]["status"], "PRESENT")
        self.assertEqual(summary["recent"][0]["subject_code"], "CS-102")
        self.assertEqual(summary["recent"][1]["status"], "ABSENT")
        self.assertEqual(len(summary["monthly_trend"]), 2)
        self.assertEqual(summary["monthly_trend"][-1]["total_classes"], 1)

    def test_only_this_students_records_are_aggregated(self):
        other = make_student(self.graph, index=2)
        self._record(self.computer_science, AttendanceStatus.PRESENT, days_ago=0)
        add_attendance(
            student=other,
            subject=self.computer_science,
            class_room=self.graph.class_room,
            status=AttendanceStatus.ABSENT,
            days_ago=0,
        )

        summary = attendance_summary(self.profile)

        self.assertEqual(summary["total_classes"], 1)
        self.assertEqual(summary["overall_percentage"], 100.0)


class AttendanceApiTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)

    def test_the_endpoint_exposes_the_unavailable_envelope(self):
        response = self.as_user(self.profile.user).get("/api/student/attendance/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["message"], "No attendance data available yet.")
        self.assertEqual(body["subjects"], [])
        self.assertIsNone(body["overall_percentage"])
        self.assertIsNone(body.get("lowest_subject"))
        self.assertEqual(body["counts"], ALL_LABELS_ZERO)
        self.assertEqual(body["target_percentage"], 75.0)
        self.assertFalse(body["meets_target"])

    def test_the_endpoint_reports_present_late_and_excused_as_attended(self):
        for offset, status in enumerate(
            [
                AttendanceStatus.PRESENT,
                AttendanceStatus.LATE,
                AttendanceStatus.EXCUSED,
                AttendanceStatus.ABSENT,
            ]
        ):
            add_attendance(
                student=self.profile,
                subject=self.graph.subject("CS-101"),
                class_room=self.graph.class_room,
                status=status,
                days_ago=offset,
            )

        body = self.as_user(self.profile.user).get("/api/student/attendance/").json()

        self.assertTrue(body["available"])
        self.assertEqual(body["attended_classes"], 3)
        self.assertEqual(body["total_classes"], 4)
        self.assertEqual(body["overall_percentage"], 75.0)
        self.assertTrue(body["meets_target"])
        self.assertEqual(body["counts"]["Late"], 1)
        self.assertEqual(body["counts"]["Excused"], 1)
        self.assertEqual(body["counts"]["Absent"], 1)
        self.assertEqual(body["subjects"][0]["subject_code"], "CS-101")
        self.assertEqual(body["lowest_subject"]["subject_code"], "CS-101")

    def test_the_endpoint_marks_a_poor_record_as_below_target(self):
        for offset in range(4):
            add_attendance(
                student=self.profile,
                subject=self.graph.subject("CS-101"),
                class_room=self.graph.class_room,
                status=AttendanceStatus.ABSENT,
                days_ago=offset,
            )
        add_attendance(
            student=self.profile,
            subject=self.graph.subject("CS-101"),
            class_room=self.graph.class_room,
            status=AttendanceStatus.PRESENT,
            days_ago=4,
        )

        body = self.as_user(self.profile.user).get("/api/student/attendance/").json()

        self.assertEqual(body["overall_percentage"], 20.0)
        self.assertFalse(body["meets_target"])
        self.assertEqual(body["target_percentage"], 75.0)

    def test_the_endpoint_sorts_subject_rows_worst_first(self):
        for offset in range(3):
            add_attendance(
                student=self.profile,
                subject=self.graph.subject("CS-102"),
                class_room=self.graph.class_room,
                status=AttendanceStatus.ABSENT,
                days_ago=offset,
            )
        add_attendance(
            student=self.profile,
            subject=self.graph.subject("CS-101"),
            class_room=self.graph.class_room,
            status=AttendanceStatus.PRESENT,
        )
        body = self.as_user(self.profile.user).get("/api/student/attendance/").json()

        self.assertEqual([row["subject_code"] for row in body["subjects"]], ["CS-102", "CS-101"])
        self.assertEqual(body["lowest_subject"]["subject_code"], "CS-102")

    def test_the_records_endpoint_only_returns_the_students_own_records(self):
        for offset in range(2):
            add_attendance(
                student=self.profile,
                subject=self.graph.subject("CS-101"),
                class_room=self.graph.class_room,
                status=AttendanceStatus.PRESENT,
                days_ago=offset,
            )
        other = make_student(self.graph, index=2)
        add_attendance(
            student=other,
            subject=self.graph.subject("CS-101"),
            class_room=self.graph.class_room,
            status=AttendanceStatus.ABSENT,
        )

        response = self.as_user(self.profile.user).get("/api/student/attendance/records/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual({row["status"] for row in body["results"]}, {"PRESENT"})
        self.assertEqual({row["subject_code"] for row in body["results"]}, {"CS-101"})
        self.assertEqual({row["status_label"] for row in body["results"]}, {"Present"})
