"""
Result and paper publication workflows.

Both follow the same rule: nothing reaches a student until an explicit publish
action, and every transition is recorded.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from assessment.models import (
    Paper,
    PaperStatus,
    Result,
    ResultPublication,
    ResultStatus,
)
from common.exceptions import InvalidWorkflowTransition, TelAPIException
from core.audit import log_event
from core.notifications import notify

RESULT_TRANSITIONS: dict[str, set[str]] = {
    ResultStatus.SUBMITTED: {ResultStatus.DRAFT},
    ResultStatus.VERIFIED: {ResultStatus.SUBMITTED},
    ResultStatus.PUBLISHED: {ResultStatus.VERIFIED},
    ResultStatus.DRAFT: {ResultStatus.VERIFIED},
}

PAPER_TRANSITIONS: dict[str, set[str]] = {
    PaperStatus.COMPLETED: {PaperStatus.DRAFT},
    PaperStatus.VERIFIED: {PaperStatus.COMPLETED},
    PaperStatus.PUBLISHED: {PaperStatus.VERIFIED},
    PaperStatus.PRACTICE_AVAILABLE: {PaperStatus.PUBLISHED, PaperStatus.VERIFIED},
    PaperStatus.ARCHIVED: {
        PaperStatus.PUBLISHED,
        PaperStatus.PRACTICE_AVAILABLE,
        PaperStatus.VERIFIED,
    },
    PaperStatus.DRAFT: {PaperStatus.PRACTICE_AVAILABLE, PaperStatus.PUBLISHED, PaperStatus.VERIFIED},
}


def grade_for(percentage: float) -> str:
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


@transaction.atomic
def create_result(*, student, subject, paper, data: dict, actor) -> Result:
    try:
        total = Decimal(str(data["total_marks"]))
        obtained = Decimal(str(data["obtained_marks"]))
    except (KeyError, InvalidOperation):
        raise TelAPIException("Total and obtained marks must be numbers.")
    if obtained > total:
        raise TelAPIException("Obtained marks cannot exceed the total marks.")
    if total <= 0:
        raise TelAPIException("Total marks must be greater than zero.")

    percentage = round(float(obtained / total * 100), 2)
    result = Result.objects.create(
        student=student,
        subject=subject,
        paper=paper,
        assessment_name=data["assessment_name"][:200],
        assessment_type=data["assessment_type"],
        assessment_date=data["assessment_date"],
        total_marks=total,
        obtained_marks=obtained,
        percentage=percentage,
        grade=data.get("grade") or grade_for(float(percentage)),
        position_in_class=data.get("position_in_class"),
        remarks=(data.get("remarks") or "")[:240],
        status=ResultStatus.DRAFT,
        entered_by=actor,
    )
    ResultPublication.objects.create(
        result=result, from_status="", to_status=ResultStatus.DRAFT, actor=actor
    )
    log_event(
        None, action="result.created", user=actor, entity=result,
        summary=f"{data['assessment_name']} entered for {student.student_code}",
        metadata={"percentage": float(percentage)},
    )
    return result


@transaction.atomic
def transition_result(*, result: Result, target: str, actor, note: str = "") -> Result:
    allowed = RESULT_TRANSITIONS.get(target, set())
    if result.status not in allowed:
        raise InvalidWorkflowTransition(
            f"A result in '{result.get_status_display()}' cannot be moved to '{ResultStatus(target).label}'."
        )

    previous = result.status
    result.status = target
    fields = ["status"]
    if target == ResultStatus.VERIFIED:
        result.verified_by = actor
        result.verified_at = timezone.now()
        fields += ["verified_by", "verified_at"]
    elif target == ResultStatus.PUBLISHED:
        result.published_by = actor
        result.published_at = timezone.now()
        fields += ["published_by", "published_at"]
    result.save(update_fields=fields)

    ResultPublication.objects.create(
        result=result, from_status=previous, to_status=target, actor=actor, note=note[:240]
    )
    log_event(
        None, action=f"result.{target.lower()}", user=actor, entity=result,
        summary=f"{result.assessment_name} → {ResultStatus(target).label}", metadata={"note": note},
    )

    if target == ResultStatus.PUBLISHED:
        notify(
            result.student.user,
            category="RESULT",
            title="A new result has been published",
            body=(
                f"{result.assessment_name} — {result.subject.name}: "
                f"{float(result.obtained_marks):g} / {float(result.total_marks):g} "
                f"({float(result.percentage):.0f}%)."
            ),
            action_url="/results",
            action_label="View result",
            dedupe_key=f"result-published:{result.pk}",
        )
    return result


@transaction.atomic
def transition_paper(*, paper: Paper, target: str, actor, release_at=None) -> Paper:
    allowed = PAPER_TRANSITIONS.get(target, set())
    if paper.status not in allowed:
        raise InvalidWorkflowTransition(
            f"A paper in '{paper.get_status_display()}' cannot be moved to '{PaperStatus(target).label}'."
        )
    if target == PaperStatus.PRACTICE_AVAILABLE and not paper.questions.exists():
        raise TelAPIException("Add at least one question before opening the paper for practice.")

    previous = paper.status
    paper.status = target
    fields = ["status"]
    if target == PaperStatus.VERIFIED:
        paper.verified_by = actor
        paper.verified_at = timezone.now()
        fields += ["verified_by", "verified_at"]
    if target in {PaperStatus.PUBLISHED, PaperStatus.PRACTICE_AVAILABLE}:
        paper.published_at = paper.published_at or timezone.now()
        if release_at:
            paper.release_at = release_at
        fields += ["published_at", "release_at"]
        if target == PaperStatus.ARCHIVED:
            paper.is_archived = True
            fields.append("is_archived")
    paper.save(update_fields=fields)

    log_event(
        None, action=f"paper.{target.lower()}", user=actor, entity=paper,
        summary=f"{paper.title} → {PaperStatus(target).label}",
        metadata={"previous": previous},
    )

    if target in {PaperStatus.PUBLISHED, PaperStatus.PRACTICE_AVAILABLE}:
        from core.notifications import notify_class

        notify_class(
            class_room=paper.class_room,
            section=paper.section,
            category="PAPER",
            title="A new paper is available in the practice archive",
            body=f"{paper.title} — {paper.subject.name} ({paper.get_exam_type_display()}).",
            action_url=f"/papers/{paper.pk}",
            action_label="Open paper",
            dedupe_suffix=f"paper-{paper.pk}-{target}",
        )
    return paper
