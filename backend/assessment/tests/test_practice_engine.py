"""
Practice engine: question delivery, auto grading, pending manual review,
idempotent submission and attempt limits.
"""

from __future__ import annotations

from assessment import practice
from assessment.models import (
    AttemptStatus,
    PaperStatus,
    PracticeAnswer,
    PracticeAttempt,
    QuestionType,
)
from common.tests.base import ApiTestCase
from common.tests.factories import add_question, build_class, make_paper, make_student

# question_id -> (question type, marks, correct option index)
QUESTION_PLAN = [
    (QuestionType.MCQ, 1, 0),
    (QuestionType.MCQ, 1, 2),
    (QuestionType.TRUE_FALSE, 2, 1),
    (QuestionType.TRUE_FALSE, 2, 0),
    (QuestionType.SHORT, 3, None),
    (QuestionType.SUBJECTIVE, 5, None),
]
TOTAL_MARKS = 14  # 1 + 1 + 2 + 2 + 3 + 5


class PracticePaperMixin:
    def setUp(self):
        super().setUp()
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.paper = make_paper(
            self.graph, status=PaperStatus.PRACTICE_AVAILABLE, total_marks=TOTAL_MARKS
        )
        self.questions = [
            add_question(
                self.paper,
                order=index + 1,
                question_type=question_type,
                marks=marks,
                correct_option=correct,
            )
            for index, (question_type, marks, correct) in enumerate(QUESTION_PLAN)
        ]

    # -- helpers -----------------------------------------------------------

    def start(self):
        response = self.as_user(self.profile.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def save(self, attempt_id, answers):
        return self.as_user(self.profile.user).post(
            f"/api/practice/{attempt_id}/save/", {"answers": answers}, format="json"
        )

    def submit(self, attempt_id, answers=None):
        payload = {} if answers is None else {"answers": answers}
        return self.as_user(self.profile.user).post(
            f"/api/practice/{attempt_id}/submit/", payload, format="json"
        )

    def review(self, attempt_id):
        return self.as_user(self.profile.user).get(f"/api/practice/{attempt_id}/review/")


class StartingAnAttemptTests(PracticePaperMixin, ApiTestCase):
    def test_the_answer_key_is_never_delivered_with_the_questions(self):
        response = self.as_user(self.profile.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(len(body["questions"]), 6)
        self.assertEqual(body["resume"], False)
        self.assertEqual(body["attempt_number"], 1)
        self.assertEqual(body["saved_answers"], [])
        self.assertEqual(body["paper"]["id"], self.paper.pk)

        for question in body["questions"]:
            with self.subTest(order=question["order"]):
                self.assertEqual(
                    set(question),
                    {"id", "order", "question_type", "text", "options", "marks", "chapter"},
                )
                self.assertNotIn("correct_option", question)
                self.assertNotIn("answer_key_text", question)
                self.assertNotIn("explanation", question)

        # Belt and braces: the stored key is nowhere in the response body.
        raw = response.content.decode()
        self.assertNotIn("correct_option", raw)
        self.assertNotIn("answer_key_text", raw)

    def test_resuming_returns_the_same_attempt_and_the_saved_answers(self):
        first = self.start()
        attempt_id = first["attempt_id"]
        self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 1}])

        second = self.start()

        self.assertEqual(second["attempt_id"], attempt_id)
        self.assertEqual(second["resume"], True)
        self.assertEqual(
            second["saved_answers"],
            [{"question_id": self.questions[0].pk, "selected_option": 1, "text_answer": ""}],
        )
        self.assertEqual(PracticeAttempt.objects.filter(paper=self.paper).count(), 1)

    def test_a_draft_paper_cannot_be_started(self):
        self.paper.status = PaperStatus.DRAFT
        self.paper.save(update_fields=["status"])

        response = self.as_user(self.profile.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        )

        self.assertEqual(response.status_code, 404, msg=response.content)
        self.assertEqual(PracticeAttempt.objects.count(), 0)

    def test_a_paper_without_questions_cannot_be_started(self):
        empty = make_paper(
            self.graph, title="Empty paper", status=PaperStatus.PRACTICE_AVAILABLE
        )

        response = self.as_user(self.profile.user).post(
            f"/api/papers/{empty.pk}/practice/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertEqual(
            response.json()["error"]["message"], "This paper is not open for practice."
        )
        self.assertEqual(PracticeAttempt.objects.count(), 0)


class AutoGradingTests(PracticePaperMixin, ApiTestCase):
    def test_mcq_and_true_false_are_auto_graded(self):
        attempt_id = self.start()["attempt_id"]
        answers = [
            {"question_id": self.questions[0].pk, "selected_option": 0},  # correct
            {"question_id": self.questions[1].pk, "selected_option": 0},  # wrong (key is 2)
            {"question_id": self.questions[2].pk, "selected_option": 0},  # wrong (key is 1)
            {"question_id": self.questions[3].pk, "selected_option": 1},  # wrong (key is 0)
        ]
        self.assertEqual(self.save(attempt_id, answers).status_code, 200)

        response = self.submit(attempt_id)

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["score"], 1.0)
        self.assertEqual(body["total_marks"], float(TOTAL_MARKS))
        self.assertEqual(body["percentage"], 7.14)
        self.assertEqual(body["grade"], "E")
        self.assertEqual(body["correct"], 1)
        self.assertEqual(body["incorrect"], 3)
        self.assertEqual(body["unanswered"], 2)
        self.assertEqual(body["pending_review"], 0)
        self.assertEqual(body["notes"], "")

        attempt = PracticeAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.status, AttemptStatus.GRADED)
        self.assertEqual(float(attempt.auto_graded_marks), 1.0)
        self.assertEqual(attempt.accuracy, 25.0)
        self.assertIsNotNone(attempt.submitted_at)

        graded = {
            row.question_id: (row.is_correct, float(row.marks_awarded), row.is_auto_graded)
            for row in PracticeAnswer.objects.filter(attempt=attempt)
        }
        self.assertEqual(graded[self.questions[0].pk], (True, 1.0, True))
        self.assertEqual(graded[self.questions[1].pk], (False, 0.0, True))
        self.assertEqual(graded[self.questions[2].pk], (False, 0.0, True))
        self.assertEqual(graded[self.questions[3].pk], (False, 0.0, True))
        # The two written questions were never answered, so no answer row exists.
        self.assertEqual(len(graded), 4)

    def test_a_completely_correct_attempt_scores_full_marks(self):
        attempt_id = self.start()["attempt_id"]
        answers = [
            {"question_id": question.pk, "selected_option": question.correct_option}
            for question in self.questions
            if question.correct_option is not None
        ]
        self.save(attempt_id, answers)

        body = self.submit(attempt_id).json()

        self.assertEqual(body["correct"], 4)
        self.assertEqual(body["incorrect"], 0)
        self.assertEqual(body["score"], 6.0)  # 1 + 1 + 2 + 2 auto-gradable marks
        self.assertEqual(body["percentage"], 42.86)
        self.assertEqual(body["unanswered"], 2)

    def test_subjective_answers_are_pending_review_and_not_auto_graded(self):
        attempt_id = self.start()["attempt_id"]
        answers = [
            {"question_id": self.questions[4].pk, "text_answer": "Newton's third law."},
            {"question_id": self.questions[5].pk, "text_answer": "A full worked explanation."},
        ]
        self.assertEqual(self.save(attempt_id, answers).status_code, 200)

        body = self.submit(attempt_id).json()

        self.assertEqual(body["pending_review"], 2)
        self.assertEqual(body["correct"], 0)
        self.assertEqual(body["incorrect"], 0)
        self.assertEqual(body["unanswered"], 4)
        self.assertEqual(body["score"], 0.0)
        self.assertEqual(body["total_marks"], float(TOTAL_MARKS))
        self.assertEqual(body["percentage"], 0.0)
        self.assertEqual(body["grade"], "E")
        self.assertIn("covers auto-graded questions only", body["notes"])

        attempt = PracticeAttempt.objects.get(pk=attempt_id)
        # Pending review keeps the attempt in SUBMITTED, never auto-completed.
        self.assertEqual(attempt.status, AttemptStatus.SUBMITTED)
        self.assertEqual(attempt.manual_review_count, 2)
        self.assertEqual(float(attempt.auto_graded_marks), 0.0)
        for answer in PracticeAnswer.objects.filter(attempt=attempt):
            with self.subTest(question=answer.question_id):
                self.assertIsNone(answer.is_correct)
                self.assertFalse(answer.is_auto_graded)
                self.assertEqual(float(answer.marks_awarded), 0.0)
        self.assertEqual(
            sorted(PracticeAnswer.objects.filter(attempt=attempt).values_list("question_id", flat=True)),
            sorted([self.questions[4].pk, self.questions[5].pk]),
        )

    def test_an_out_of_range_option_is_treated_as_unanswered(self):
        attempt_id = self.start()["attempt_id"]
        self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 99}])

        body = self.submit(attempt_id).json()

        self.assertEqual(body["unanswered"], 6)
        self.assertEqual(body["score"], 0.0)
        self.assertEqual(PracticeAnswer.objects.filter(attempt_id=attempt_id).count(), 0)

    def test_saving_answers_after_submission_is_refused(self):
        attempt_id = self.start()["attempt_id"]
        self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 0}])
        self.assertEqual(self.submit(attempt_id).status_code, 200)

        response = self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 2}])

        self.assertEqual(response.status_code, 409, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "conflict")
        answer = PracticeAnswer.objects.get(attempt_id=attempt_id)
        self.assertEqual(answer.selected_option, 0)
        self.assertTrue(answer.is_correct)


class IdempotentSubmissionTests(PracticePaperMixin, ApiTestCase):
    def test_submitting_twice_does_not_double_count_or_crash(self):
        attempt_id = self.start()["attempt_id"]
        self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 0}])
        first = self.submit(attempt_id)
        self.assertEqual(first.status_code, 200, msg=first.content)
        attempt = PracticeAttempt.objects.get(pk=attempt_id)
        submitted_at = attempt.submitted_at

        second = self.submit(attempt_id)
        third = self.submit(attempt_id)

        for index, response in enumerate((second, third), start=2):
            with self.subTest(submission=index):
                self.assertEqual(response.status_code, 200, msg=response.content)
                for field in ("score", "total_marks", "percentage", "correct", "incorrect",
                              "unanswered", "pending_review", "attempt_number"):
                    self.assertEqual(response.json()[field], first.json()[field])

        attempt.refresh_from_db()
        self.assertEqual(PracticeAnswer.objects.filter(attempt=attempt).count(), 1)
        self.assertEqual(PracticeAttempt.objects.filter(paper=self.paper).count(), 1)
        self.assertEqual(float(attempt.score), first.json()["score"])
        self.assertEqual(attempt.submitted_at, submitted_at)

    def test_every_submit_request_is_audited_but_the_attempt_is_graded_once(self):
        from core.models import AuditLog

        attempt_id = self.start()["attempt_id"]
        self.submit(attempt_id)
        self.submit(attempt_id)

        entries = AuditLog.objects.filter(action="practice.submitted")
        self.assertEqual(entries.count(), 2)  # one per HTTP request, both idempotent
        self.assertEqual({row.actor for row in entries}, {self.profile.user})
        self.assertEqual(PracticeAttempt.objects.filter(paper=self.paper).count(), 1)

    def test_the_service_returns_created_not_resumed(self):
        attempt, created = practice.start_attempt(paper=self.paper, student=self.profile)
        self.assertTrue(created)
        self.assertEqual(attempt.status, "IN_PROGRESS")

        resumed_attempt, created_again = practice.start_attempt(
            paper=self.paper, student=self.profile
        )

        self.assertFalse(created_again)
        self.assertEqual(resumed_attempt.pk, attempt.pk)


class ForeignQuestionTests(PracticePaperMixin, ApiTestCase):
    def test_answers_for_questions_of_another_paper_are_ignored(self):
        other_paper = make_paper(
            self.graph, title="Other paper", status=PaperStatus.PRACTICE_AVAILABLE
        )
        foreign = add_question(
            other_paper, order=1, question_type=QuestionType.MCQ, marks=50, correct_option=0
        )
        self.assertNotEqual(foreign.pk, self.questions[0].pk)

        attempt_id = self.start()["attempt_id"]
        response = self.save(
            attempt_id,
            [
                {"question_id": self.questions[0].pk, "selected_option": 0},
                {"question_id": foreign.pk, "selected_option": 0},
            ],
        )
        self.assertEqual(response.status_code, 200, msg=response.content)

        attempt = PracticeAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.answers.count(), 1)
        self.assertEqual(attempt.answers.get().question_id, self.questions[0].pk)

        body = self.submit(attempt_id).json()
        # The foreign question contributes neither marks nor a counted answer.
        self.assertEqual(body["total_marks"], float(TOTAL_MARKS))
        self.assertEqual(body["score"], 1.0)
        self.assertEqual(body["correct"], 1)
        self.assertEqual(body["unanswered"], 5)
        self.assertEqual(body["correct"] + body["incorrect"] + body["unanswered"], 6)


class AnswerKeyAvailabilityTests(PracticePaperMixin, ApiTestCase):
    def test_the_answer_key_is_unavailable_before_submission(self):
        attempt_id = self.start()["attempt_id"]

        response = self.review(attempt_id)

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertEqual(
            response.json()["error"]["message"],
            "Submit the attempt before viewing the answer key.",
        )
        self.assertNotIn("correct_option", response.content.decode())

    def test_the_answer_key_is_available_after_submission(self):
        attempt_id = self.start()["attempt_id"]
        self.save(
            attempt_id,
            [
                {"question_id": self.questions[0].pk, "selected_option": 0},
                {"question_id": self.questions[4].pk, "text_answer": "A written answer."},
            ],
        )
        self.submit(attempt_id)

        response = self.review(attempt_id)

        self.assertEqual(response.status_code, 200, msg=response.content)
        review = {row["order"]: row for row in response.json()["review"]}
        self.assertEqual(len(review), 6)

        # The objective question carries its key and explanation.
        self.assertEqual(review[1]["correct_option"], 0)
        self.assertTrue(review[1]["is_auto_graded"])
        self.assertTrue(review[1]["is_correct"])
        self.assertEqual(review[1]["marks_awarded"], 1.0)
        self.assertFalse(review[1]["pending_review"])

        # A written answer is never handed a key.
        self.assertIsNone(review[5]["correct_option"])
        self.assertTrue(review[5]["pending_review"])
        self.assertIsNone(review[5]["is_correct"])
        self.assertEqual(review[5]["text_answer"], "A written answer.")

        # An unanswered question is reported as such.
        self.assertIsNone(review[2]["selected_option"])
        self.assertFalse(review[2]["is_auto_graded"])
        self.assertEqual(review[2]["marks_awarded"], 0.0)

        self.assertIn("pending teacher review", response.json()["message"])

    def test_a_paper_can_withhold_the_answer_key(self):
        self.paper.show_answers_after_submit = False
        self.paper.save(update_fields=["show_answers_after_submit"])
        attempt_id = self.start()["attempt_id"]
        self.submit(attempt_id)

        response = self.review(attempt_id)

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertEqual(
            response.json()["error"]["message"],
            "The answer key for this paper is not published.",
        )


class AttemptLimitTests(PracticePaperMixin, ApiTestCase):
    def _run_and_submit(self):
        attempt_id = self.start()["attempt_id"]
        self.save(attempt_id, [{"question_id": self.questions[0].pk, "selected_option": 0}])
        self.assertEqual(self.submit(attempt_id).status_code, 200)
        return attempt_id

    def test_the_attempt_limit_is_enforced_once_reached(self):
        self.paper.attempt_limit = 1
        self.paper.save(update_fields=["attempt_limit"])
        self._run_and_submit()

        allowed, reason = practice.can_attempt(self.paper, self.profile)
        self.assertFalse(allowed)
        self.assertEqual(reason, "This paper allows 1 attempt(s).")

        response = self.as_user(self.profile.user).post(
            f"/api/papers/{self.paper.pk}/practice/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertEqual(response.json()["error"]["message"], "This paper allows 1 attempt(s).")
        self.assertEqual(
            PracticeAttempt.objects.filter(paper=self.paper, student=self.profile).count(), 1
        )

    def test_a_second_attempt_is_allowed_while_below_the_limit(self):
        self.paper.attempt_limit = 2
        self.paper.save(update_fields=["attempt_limit"])
        self._run_and_submit()

        second = self.start()

        self.assertEqual(second["attempt_number"], 2)
        self.assertEqual(PracticeAttempt.objects.filter(paper=self.paper).count(), 2)

    def test_an_in_progress_attempt_does_not_consume_the_limit(self):
        self.paper.attempt_limit = 1
        self.paper.save(update_fields=["attempt_limit"])
        self.start()

        allowed, reason = practice.can_attempt(self.paper, self.profile)

        self.assertTrue(allowed, reason)
        self.assertEqual(
            PracticeAttempt.objects.filter(
                paper=self.paper, student=self.profile, status=AttemptStatus.SUBMITTED
            ).count(),
            0,
        )

    def test_a_zero_limit_means_unlimited(self):
        self.paper.attempt_limit = 0
        self.paper.save(update_fields=["attempt_limit"])
        for _ in range(3):
            self._run_and_submit()

        allowed, reason = practice.can_attempt(self.paper, self.profile)

        self.assertTrue(allowed, reason)
        self.assertEqual(PracticeAttempt.objects.filter(paper=self.paper).count(), 3)

    def test_a_single_attempt_paper_refuses_a_retake(self):
        self.paper.allow_retake = False
        self.paper.save(update_fields=["allow_retake"])
        self._run_and_submit()

        allowed, reason = practice.can_attempt(self.paper, self.profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "This paper allows a single attempt only.")

    def test_an_inactive_student_cannot_attempt(self):
        from accounts.models import StudentProfile

        StudentProfile.objects.filter(pk=self.profile.pk).update(status="ON_LEAVE")
        self.profile.refresh_from_db()

        allowed, reason = practice.can_attempt(self.paper, self.profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "Your student record is not active.")


class PracticeHistoryTests(PracticePaperMixin, ApiTestCase):
    def test_history_only_lists_the_students_own_attempts(self):
        own_id = self.start()["attempt_id"]
        self.submit(own_id)

        response = self.as_user(self.profile.user).get("/api/student/practice-history/")

        self.assertEqual(response.status_code, 200, msg=response.content)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["attempt_id"], own_id)
        self.assertEqual(body["results"][0]["paper_id"], self.paper.pk)
        self.assertEqual(body["results"][0]["percentage"], 0.0)
