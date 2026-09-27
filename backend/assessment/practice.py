"""
Practice engine.

Rules that keep grading honest:

* Only MCQ and True/False with a stored correct option are auto-graded.
* Short and subjective answers are recorded, marked *pending review*, and
  excluded from the auto-graded score. The response says so explicitly instead
  of inventing a mark.
* Scores are always derived from the stored question set and the student's saved
  answers — nothing is precomputed in the client.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from assessment.models import (
    AttemptStatus,
    Paper,
    PaperQuestion,
    PracticeAnswer,
    PracticeAttempt,
)
from common.exceptions import Conflict, TelAPIException


def can_attempt(paper: Paper, student) -> tuple[bool, str]:
    if not paper.is_visible_to_students:
        return False, "This paper is not available."
    if not paper.is_practice_enabled:
        return False, "This paper is not open for practice."
    if student.status != "ACTIVE":
        return False, "Your student record is not active."
    if not paper.allow_retake:
        completed = PracticeAttempt.objects.filter(
            paper=paper, student=student
        ).completed()
        if completed.exists():
            return False, "This paper allows a single attempt only."
    if paper.attempt_limit:
        count = PracticeAttempt.objects.filter(paper=paper, student=student).completed().count()
        if count >= paper.attempt_limit:
            return False, f"This paper allows {paper.attempt_limit} attempt(s)."
    return True, ""


@transaction.atomic
def start_attempt(*, paper: Paper, student) -> tuple[PracticeAttempt, bool]:
    allowed, reason = can_attempt(paper, student)
    if not allowed:
        raise TelAPIException(reason)

    resumed = (
        PracticeAttempt.objects.select_for_update()
        .filter(paper=paper, student=student, status=AttemptStatus.IN_PROGRESS)
        .first()
    )
    if resumed is not None:
        return resumed, False

    last_number = (
        PracticeAttempt.objects.filter(paper=paper, student=student)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
        or 0
    )
    attempt = PracticeAttempt.objects.create(
        paper=paper,
        student=student,
        attempt_number=last_number + 1,
        total_marks=sum((q.marks for q in paper.questions.all()), Decimal("0")),
        started_at=timezone.now(),
    )
    return attempt, True


def _validate_answers(paper: Paper, answers) -> dict[int, dict]:
    questions = {q.id: q for q in paper.questions.all()}
    cleaned: dict[int, dict] = {}
    for raw in answers or []:
        question_id = raw.get("question_id")
        question = questions.get(question_id)
        if question is None:
            # Silently ignore ids that are not part of this paper rather than
            # trusting a client supplied question set.
            continue
        selected = raw.get("selected_option")
        if selected is not None:
            try:
                selected = int(selected)
            except (TypeError, ValueError):
                selected = None
        option_count = len(question.options or [])
        if selected is not None and not (0 <= selected < option_count):
            selected = None
        text = str(raw.get("text_answer") or "")[:4000]
        if selected is None and not text.strip():
            continue
        cleaned[question_id] = {"selected_option": selected, "text_answer": text}
    return cleaned


@transaction.atomic
def save_answers(*, attempt: PracticeAttempt, answers) -> PracticeAttempt:
    if attempt.is_complete:
        raise Conflict("This attempt has already been submitted.")
    cleaned = _validate_answers(attempt.paper, answers)
    PracticeAnswer.objects.filter(attempt=attempt).delete()
    PracticeAnswer.objects.bulk_create(
        [
            PracticeAnswer(
                attempt=attempt,
                question_id=question_id,
                selected_option=payload["selected_option"],
                text_answer=payload["text_answer"],
            )
            for question_id, payload in cleaned.items()
        ]
    )
    attempt.last_saved_at = timezone.now()
    attempt.save(update_fields=["last_saved_at", "updated_at"])
    return attempt


@transaction.atomic
def submit_attempt(*, attempt: PracticeAttempt) -> PracticeAttempt:
    if attempt.is_complete:
        return attempt

    questions = list(PaperQuestion.objects.filter(paper=attempt.paper).order_by("order", "id"))
    if not questions:
        raise TelAPIException("This paper has no questions yet.")

    existing = {a.question_id: a for a in PracticeAnswer.objects.filter(attempt=attempt)}
    answer_rows: list[PracticeAnswer] = []

    score = Decimal("0")
    total = Decimal("0")
    correct = incorrect = unanswered = pending = 0
    auto_marks = Decimal("0")

    for question in questions:
        total += Decimal(question.marks)
        answer = existing.get(question.id)
        if answer is None:
            unanswered += 1
            continue

        if question.is_auto_gradable:
            is_correct = answer.selected_option == question.correct_option
            awarded = Decimal(question.marks) if is_correct else Decimal("0")
            answer.is_correct = is_correct
            answer.is_auto_graded = True
            answer.marks_awarded = awarded
            score += awarded
            auto_marks += awarded
            correct += int(is_correct)
            incorrect += int(not is_correct)
        else:
            answer.is_correct = None
            answer.is_auto_graded = False
            answer.marks_awarded = Decimal("0")
            pending += 1
        answer_rows.append(answer)

    if answer_rows:
        PracticeAnswer.objects.bulk_update(
            answer_rows, ["is_correct", "is_auto_graded", "marks_awarded"]
        )

    submitted_at = timezone.now()
    attempt.status = AttemptStatus.GRADED if pending == 0 else AttemptStatus.SUBMITTED
    attempt.submitted_at = submitted_at
    attempt.time_taken_seconds = max(
        0, int((submitted_at - attempt.started_at).total_seconds())
    )
    attempt.score = score
    attempt.total_marks = total
    attempt.percentage = round(float(score / total) * 100, 2) if total else None
    attempt.correct_count = correct
    attempt.incorrect_count = incorrect
    attempt.unanswered_count = unanswered
    attempt.manual_review_count = pending
    attempt.auto_graded_marks = auto_marks
    attempt.save()
    return attempt


def grade_for(percentage: float | None) -> str:
    if percentage is None:
        return ""
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 50:
        return "D"
    return "E"


def build_review(attempt: PracticeAttempt) -> list[dict]:
    """Per-question review payload shown after submission."""

    answers = {a.question_id: a for a in PracticeAnswer.objects.filter(attempt=attempt)}
    review: list[dict] = []
    for question in PaperQuestion.objects.filter(paper=attempt.paper).order_by("order", "id"):
        answer = answers.get(question.id)
        graded = answer is not None and answer.is_auto_graded
        review.append(
            {
                "question_id": question.id,
                "order": question.order,
                "question_type": question.question_type,
                "text": question.text,
                "options": question.options or [],
                "marks": float(question.marks),
                "selected_option": answer.selected_option if answer else None,
                "text_answer": answer.text_answer if answer else "",
                "is_correct": answer.is_correct if answer else None,
                "marks_awarded": float(answer.marks_awarded) if answer else 0.0,
                "is_auto_graded": graded,
                "correct_option": question.correct_option if graded else None,
                "explanation": question.explanation if graded else "",
                "pending_review": bool(answer) and not graded,
            }
        )
    return review
