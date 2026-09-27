"""
Analytics: subject performance, weak subject detection, topic coverage and
progress. Every number must come from published results only, and the engine
must say so explicitly when the underlying data cannot support an analysis.
"""

from __future__ import annotations

from django.test import override_settings

from assessment import analytics
from assessment.models import ResultStatus
from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import add_result_item, build_class, make_result, make_student

WEAK = dict(TEL_WEAK_SUBJECT_SCORE=65.0, TEL_WEAK_SUBJECT_MIN_ATTEMPTS=2)


class SubjectPerformanceTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.maths = self.graph.subject("CS-102")
        self.physics = self.graph.subject("CS-103")

    def test_only_published_results_are_aggregated(self):
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=25,
            days_ago=30,
            assessment_name="Published low",
        )
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=35,
            days_ago=20,
            assessment_name="Published high",
        )
        # The newest maths result is still a draft and must not be counted.
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=50,
            days_ago=1,
            assessment_name="Draft perfect",
            status=ResultStatus.DRAFT,
        )
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=50,
            days_ago=2,
            assessment_name="Submitted perfect",
            status=ResultStatus.SUBMITTED,
        )
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=50,
            days_ago=3,
            assessment_name="Verified perfect",
            status=ResultStatus.VERIFIED,
        )
        make_result(
            student=self.profile,
            subject=self.physics,
            obtained_marks=50,
            days_ago=5,
            assessment_name="Physics perfect",
        )

        performance = analytics.subject_performance(self.profile)

        by_code = {row.subject_code: row for row in performance}
        self.assertEqual(sorted(by_code), ["CS-102", "CS-103"])
        maths = by_code["CS-102"]
        self.assertEqual(maths.assessments, 2)
        self.assertEqual(maths.average_percentage, 60.0)  # (50 + 70) / 2
        self.assertEqual(maths.best_percentage, 70.0)
        self.assertEqual(maths.latest_percentage, 70.0)
        self.assertEqual(maths.latest_assessment, "Published high")
        self.assertEqual([item["label"] for item in maths.trend], ["Published low", "Published high"])
        self.assertEqual(by_code["CS-103"].average_percentage, 100.0)
        self.assertEqual(analytics.overall_average(self.profile), 73.3)
        # Strongest subject first.
        self.assertEqual([row.subject_code for row in performance], ["CS-103", "CS-102"])

    def test_a_revoked_result_is_excluded(self):
        make_result(
            student=self.profile, subject=self.maths, obtained_marks=50, assessment_name="Live"
        )
        make_result(
            student=self.profile, subject=self.maths, obtained_marks=10, assessment_name="Revoked"
        )
        from assessment.models import Result

        Result.objects.filter(assessment_name="Revoked").update(is_revoked=True)

        performance = analytics.subject_performance(self.profile)
        self.assertEqual(len(performance), 1)
        self.assertEqual(performance[0].latest_assessment, "Live")
        self.assertEqual(performance[0].average_percentage, 100.0)

    def test_progress_summary_is_explicitly_unavailable_without_results(self):
        summary = analytics.progress_summary(self.profile)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["assessments"], 0)
        self.assertIn("No published results yet", summary["message"])

    def test_progress_summary_groups_by_assessment_type(self):
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=40,
            assessment_type="WEEKLY_TEST",
        )
        make_result(
            student=self.profile,
            subject=self.maths,
            obtained_marks=20,
            assessment_type="MONTHLY_TEST",
        )

        summary = analytics.progress_summary(self.profile)

        self.assertTrue(summary["available"])
        self.assertEqual(summary["assessments"], 2)
        self.assertEqual(summary["average_percentage"], 60.0)
        self.assertEqual(summary["best_percentage"], 80.0)
        self.assertEqual(summary["lowest_percentage"], 40.0)
        self.assertEqual(
            {row["assessment_type"]: row["average"] for row in summary["by_type"]},
            {"WEEKLY_TEST": 80.0, "MONTHLY_TEST": 40.0},
        )


class WeakSubjectDetectionTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.maths = self.graph.subject("CS-102")
        self.physics = self.graph.subject("CS-103")

    def _scores(self, subject, percentages, *, prefix=""):
        for index, obtained in enumerate(percentages):
            make_result(
                student=self.profile,
                subject=subject,
                total_marks=100,
                obtained_marks=obtained,
                days_ago=30 - index,
                assessment_name=f"{prefix}{subject.code} test {index + 1}",
            )

    @override_settings(**WEAK)
    def test_a_subject_below_the_threshold_is_flagged_with_a_reason(self):
        self._scores(self.maths, [50, 55, 60], prefix="Maths ")
        self._scores(self.physics, [85, 90, 95], prefix="Physics ")

        flagged = analytics.detect_weak_subjects(self.profile)

        self.assertEqual([row.subject_code for row in flagged], ["CS-102"])
        weak = flagged[0]
        self.assertEqual(weak.threshold, 65.0)
        self.assertEqual(weak.recent_average, 55.0)
        self.assertEqual(weak.assessments, 3)
        self.assertEqual(weak.severity, "moderate")
        self.assertTrue(weak.reason)
        self.assertIn("55.0%", weak.reason)
        self.assertIn("65%", weak.reason)
        self.assertIn("3 assessments", weak.reason)
        self.assertIn("10.0%", weak.reason)  # the gap below the threshold
        self.assertTrue(weak.recommendation)

    @override_settings(**WEAK)
    def test_a_subject_with_fewer_assessments_than_the_minimum_is_not_flagged(self):
        # One published assessment is below the configured minimum of two, so a
        # very low score alone is not enough to raise a weak-subject alert.
        self._scores(self.maths, [20], prefix="Maths ")

        performance = {row.subject_code: row for row in analytics.subject_performance(self.profile)}
        self.assertEqual(performance["CS-102"].assessments, 1)
        self.assertEqual(performance["CS-102"].average_percentage, 20.0)
        self.assertEqual(analytics.detect_weak_subjects(self.profile), [])

    @override_settings(**WEAK)
    def test_the_same_data_is_flagged_once_the_minimum_is_reached(self):
        self._scores(self.maths, [20], prefix="Maths ")

        with override_settings(TEL_WEAK_SUBJECT_MIN_ATTEMPTS=1):
            flagged = analytics.detect_weak_subjects(self.profile)

        self.assertEqual([row.subject_code for row in flagged], ["CS-102"])
        self.assertEqual(flagged[0].recent_average, 20.0)
        self.assertEqual(flagged[0].severity, "high")

    @override_settings(TEL_WEAK_SUBJECT_SCORE=65.0, TEL_WEAK_SUBJECT_MIN_ATTEMPTS=3)
    def test_raising_the_minimum_also_stops_the_flag(self):
        self._scores(self.maths, [20, 25], prefix="Maths ")

        self.assertEqual(analytics.detect_weak_subjects(self.profile), [])

    @override_settings(**WEAK)
    def test_unpublished_results_never_trigger_a_flag(self):
        make_result(
            student=self.profile,
            subject=self.maths,
            total_marks=100,
            obtained_marks=10,
            days_ago=30,
            assessment_name="Draft failure",
            status=ResultStatus.DRAFT,
        )
        make_result(
            student=self.profile,
            subject=self.maths,
            total_marks=100,
            obtained_marks=10,
            days_ago=20,
            assessment_name="Verified failure",
            status=ResultStatus.VERIFIED,
        )

        self.assertEqual(analytics.detect_weak_subjects(self.profile), [])

    @override_settings(**WEAK)
    def test_a_severe_subject_is_reported_as_high_severity(self):
        self._scores(self.maths, [10, 20, 30], prefix="Maths ")

        weak = analytics.detect_weak_subjects(self.profile)[0]

        self.assertEqual(weak.recent_average, 20.0)
        self.assertEqual(weak.severity, "high")

    @override_settings(**WEAK)
    def test_the_lowest_topic_is_named_in_the_reason(self):
        for index, obtained in enumerate([50, 55, 60]):
            result = make_result(
                student=self.profile,
                subject=self.maths,
                total_marks=100,
                obtained_marks=obtained,
                days_ago=30 - index,
                assessment_name=f"Maths test {index + 1}",
            )
            add_result_item(result, topic="Algebra", marks_awarded=9, marks_total=10)
            add_result_item(result, topic="Geometry", marks_awarded=2, marks_total=10)

        weak = analytics.detect_weak_subjects(self.profile)[0]

        self.assertIn("Geometry (20%)", weak.reason)


class TopicAnalysisTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.maths = self.graph.subject("CS-102")

    def test_topic_analysis_is_unavailable_when_no_result_item_carries_a_topic(self):
        result = make_result(student=self.profile, subject=self.maths)
        add_result_item(result, topic="", chapter="Core concepts", marks_awarded=6, marks_total=10)

        analysis = analytics.topic_analysis(self.profile)

        self.assertFalse(analysis["available"])
        self.assertEqual(analysis["topics"], [])
        self.assertEqual(analysis["reason"], analytics.TOPIC_ANALYSIS_UNAVAILABLE)
        self.assertIn("topic-level analysis", analysis["reason"].lower())

    def test_topic_analysis_is_unavailable_without_any_result_items(self):
        make_result(student=self.profile, subject=self.maths)

        self.assertFalse(analytics.topic_analysis(self.profile)["available"])

    def test_topic_analysis_is_unavailable_for_unpublished_results(self):
        result = make_result(
            student=self.profile, subject=self.maths, status=ResultStatus.DRAFT
        )
        add_result_item(result, topic="Algebra", marks_awarded=6, marks_total=10)

        self.assertFalse(analytics.topic_analysis(self.profile)["available"])

    def test_topic_analysis_reports_topics_once_the_data_exists(self):
        result = make_result(student=self.profile, subject=self.maths)
        add_result_item(result, topic="Algebra", marks_awarded=8, marks_total=10)
        add_result_item(result, topic="Geometry", marks_awarded=3, marks_total=10)

        analysis = analytics.topic_analysis(self.profile)

        self.assertTrue(analysis["available"])
        self.assertEqual(analysis["reason"], "")
        topics = {row["topic"]: row for row in analysis["topics"]}
        self.assertEqual(sorted(topics), ["Algebra", "Geometry"])
        self.assertEqual(topics["Algebra"]["percentage"], 80.0)
        self.assertEqual(topics["Algebra"]["status"], "strong")
        self.assertEqual(topics["Geometry"]["percentage"], 30.0)
        self.assertEqual(topics["Geometry"]["status"], "needs_attention")
        self.assertEqual(topics["Algebra"]["subject_code"], "CS-102")


class AnalyticsApiTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.maths = self.graph.subject("CS-102")

    @override_settings(**WEAK)
    def test_the_analytics_endpoint_reports_thresholds_and_weak_subjects(self):
        for index, obtained in enumerate([40, 45, 50]):
            make_result(
                student=self.profile,
                subject=self.maths,
                total_marks=100,
                obtained_marks=obtained,
                days_ago=30 - index,
            )

        response = self.as_user(self.profile.user).get("/api/student/analytics/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertTrue(body["has_results"])
        self.assertEqual(body["message"], "")
        self.assertEqual(body["thresholds"]["weak_subject_score"], 65.0)
        self.assertEqual(body["thresholds"]["weak_subject_min_attempts"], 2)
        self.assertEqual(body["subjects"][0]["subject_code"], "CS-102")
        self.assertEqual(body["weak_subjects"][0]["subject_code"], "CS-102")
        self.assertTrue(body["weak_subjects"][0]["reason"])

    def test_the_analytics_endpoint_explains_an_empty_history(self):
        response = self.as_user(self.profile.user).get("/api/student/analytics/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertFalse(body["has_results"])
        self.assertEqual(body["subjects"], [])
        self.assertIsNone(body["overall_average"])
        self.assertIn("No published results yet", body["message"])

    def test_the_topic_endpoint_returns_the_unavailable_envelope(self):
        make_result(student=self.profile, subject=self.maths)

        response = self.as_user(self.profile.user).get("/api/student/analytics/topics/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["topics"], [])
        self.assertEqual(body["reason"], analytics.TOPIC_ANALYSIS_UNAVAILABLE)

    def test_the_progress_endpoint_reports_unavailable_without_results(self):
        response = self.as_user(self.profile.user).get("/api/student/progress/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertFalse(response.json()["available"])
        self.assertEqual(response.json()["assessments"], 0)
