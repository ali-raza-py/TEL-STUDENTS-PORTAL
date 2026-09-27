"""
Timetable workflow service.

The rule enforced here: a student-submitted timetable is *never* visible to the
class until a TEL reviewer approves it and an explicit publish step runs.
Publishing is what creates notifications and retires the previous version.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from academics.models import (
    ClassRepresentative,
    Section,
    Subject,
    SubjectOffering,
    Timetable,
    TimetableEntry,
    TimetableStatus,
    TimetableSubmission,
    Weekday,
)
from common.exceptions import InvalidWorkflowTransition, TelAPIException, Forbidden
from core.audit import log_event
from core.notifications import notify, notify_class

logger = logging.getLogger("telportal.timetable")

#: Review outcomes and the transition each one implies.
REVIEW_TRANSITIONS: dict[str, set[str]] = {
    TimetableStatus.APPROVED: {TimetableStatus.SUBMITTED, TimetableStatus.UNDER_REVIEW},
    TimetableStatus.REJECTED: {
        TimetableStatus.SUBMITTED,
        TimetableStatus.UNDER_REVIEW,
        TimetableStatus.CHANGES_REQUESTED,
    },
    TimetableStatus.CHANGES_REQUESTED: {
        TimetableStatus.SUBMITTED,
        TimetableStatus.UNDER_REVIEW,
    },
    TimetableStatus.PUBLISHED: {TimetableStatus.APPROVED},
    TimetableStatus.UNDER_REVIEW: {
        TimetableStatus.SUBMITTED,
        TimetableStatus.CHANGES_REQUESTED,
    },
}

MAX_ENTRIES_PER_TIMETABLE = 60


def can_manage_class_timetable(user, class_room_id: int, section_id: int) -> bool:
    """Only the assigned class representative or TEL staff may submit for a class."""

    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.role == "ADMIN":
        return True
    if user.role == "TEACHER":
        return True
    if user.role != "CLASS_REPRESENTATIVE":
        return False
    return ClassRepresentative.objects.filter(
        user=user,
        class_room_id=class_room_id,
        section_id=section_id,
        is_active=True,
    ).exists()


def validate_entries_payload(
    payload: list, *, class_room_id: int, academic_year_id: int
) -> list[dict]:
    """
    Validates a structured timetable submission against the class's real
    subject offerings. Unknown subjects are rejected rather than stored, so a
    representative cannot invent a subject.
    """

    if not isinstance(payload, list):
        raise TelAPIException("The timetable entries must be supplied as a list.")
    if not payload:
        raise TelAPIException("Add at least one period to the timetable.")
    if len(payload) > MAX_ENTRIES_PER_TIMETABLE:
        raise TelAPIException("A weekly timetable cannot exceed 60 periods.")

    offered = {
        o.subject.code.upper(): o.subject
        for o in SubjectOffering.objects.filter(
            class_room_id=class_room_id, academic_year_id=academic_year_id, is_active=True
        ).select_related("subject")
    }

    cleaned: list[dict] = []
    seen_slots: set[tuple] = set()
    for index, raw in enumerate(payload):
        day = raw.get("day")
        start = raw.get("start")
        end = raw.get("end")
        subject_code = str(raw.get("subject_code") or "").strip().upper()

        if day not in Weekday.values:
            raise TelAPIException(f"Period {index + 1}: '{day}' is not a valid day.")
        if not _is_time(start) or not _is_time(end):
            raise TelAPIException(f"Period {index + 1}: start and end must be times (HH:MM).")
        if end <= start:
            raise TelAPIException(f"Period {index + 1}: the end time must be after the start time.")
        if subject_code not in offered:
            raise TelAPIException(
                f"Period {index + 1}: '{subject_code}' is not a subject offered to this class."
            )
        slot = (day, start)
        if slot in seen_slots:
            raise TelAPIException(
                f"{Weekday.label_for(day)} {start} is listed more than once."
            )
        seen_slots.add(slot)
        cleaned.append(
            {
                "day": day,
                "start": start,
                "end": end,
                "subject_code": subject_code,
                "room": str(raw.get("room") or "")[:64],
                "note": str(raw.get("note") or "")[:160],
            }
        )
    return cleaned


def _is_time(value) -> bool:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return False
    try:
        hour, minute = int(value[:2]), int(value[3:])
    except ValueError:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


@transaction.atomic
def create_submission(*, user, class_room, section, academic_year, summary, change_note, payload=None, image=None, pdf=None) -> TimetableSubmission:
    if not can_manage_class_timetable(user, class_room.pk, section.pk):
        raise Forbidden("You are not the timetable manager for this class.")

    if not (summary or change_note or payload or image or pdf):
        raise TelAPIException("Describe the timetable change before submitting.")

    payload = validate_entries_payload(
        payload or [], class_room_id=class_room.pk, academic_year_id=academic_year.pk
    ) if payload else []

    open_submission = (
        TimetableSubmission.objects.filter(class_room=class_room, section=section)
        .filter(
            status__in=[
                TimetableStatus.SUBMITTED,
                TimetableStatus.UNDER_REVIEW,
                TimetableStatus.CHANGES_REQUESTED,
            ]
        )
        .first()
    )
    if open_submission is not None:
        raise InvalidWorkflowTransition(
            "A timetable submission for this class is already awaiting review."
        )

    submission = TimetableSubmission.objects.create(
        class_room=class_room,
        section=section,
        academic_year=academic_year,
        submitted_by=user,
        summary=summary[:240],
        change_note=change_note,
        entries_payload=payload,
        image_file=image,
        pdf_file=pdf,
        status=TimetableStatus.SUBMITTED,
    )
    log_event(
        None,
        action="timetable.submitted",
        user=user,
        entity=submission,
        summary=f"Timetable submitted for {class_room.code} / {section.name}",
        metadata={"entry_count": len(payload), "has_image": bool(image), "has_pdf": bool(pdf)},
    )
    return submission


@transaction.atomic
def review_submission(*, submission: TimetableSubmission, reviewer, decision: str, note: str = "") -> TimetableSubmission:
    allowed = REVIEW_TRANSITIONS.get(decision, set())
    if submission.status not in allowed:
        raise InvalidWorkflowTransition(
            f"A submission that is '{submission.get_status_display()}' cannot be moved to '{decision}'."
        )

    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.review_note = note
    submission.status = decision
    if decision == TimetableStatus.UNDER_REVIEW:
        submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
    else:
        submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    log_event(
        None,
        action=f"timetable.reviewed.{decision.lower()}",
        user=reviewer,
        entity=submission,
        summary=f"{submission.get_status_display()} — {submission.summary or 'Timetable submission'}",
        metadata={"note": note},
    )

    if submission.submitted_by_id and decision in {
        TimetableStatus.REJECTED,
        TimetableStatus.CHANGES_REQUESTED,
    }:
        titles = {
            TimetableStatus.REJECTED: "Timetable submission rejected",
            TimetableStatus.CHANGES_REQUESTED: "Timetable changes requested",
        }
        notify(
            submission.submitted_by,
            category="TIMETABLE",
            title=titles[decision],
            body=note or "Your class timetable submission was reviewed by TEL.",
            action_url=f"/class-tools/submissions/{submission.pk}",
            action_label="View submission",
            dedupe_key=f"timetable-review:{submission.pk}:{decision}",
        )
    return submission


@transaction.atomic
def publish_timetable(*, timetable: Timetable, publisher, effective_from=None, change_note: str = "") -> Timetable:
    if timetable.status not in {TimetableStatus.APPROVED, TimetableStatus.PUBLISHED}:
        raise InvalidWorkflowTransition(
            "Only an approved timetable can be published."
        )

    previous = (
        Timetable.objects.filter(
            class_room=timetable.class_room,
            section=timetable.section,
            academic_year=timetable.academic_year,
            status=TimetableStatus.PUBLISHED,
        )
        .exclude(pk=timetable.pk)
        .select_related()
        .first()
    )
    previous_snapshot = None
    if previous is not None:
        previous_snapshot = {
            (e.day_of_week, e.start_time): e.subject_id
            for e in previous.entries.all()
        }
        previous.status = TimetableStatus.ARCHIVED
        previous.archived_at = timezone.now()
        previous.save(update_fields=["status", "archived_at", "updated_at"])

    now = timezone.now()
    timetable.status = TimetableStatus.PUBLISHED
    timetable.published_at = now
    timetable.approved_by = publisher
    timetable.approved_at = timetable.approved_at or now
    if effective_from:
        timetable.effective_from = effective_from
    if change_note:
        timetable.change_note = change_note
    timetable.save(
        update_fields=[
            "status",
            "published_at",
            "approved_by",
            "approved_at",
            "effective_from",
            "change_note",
            "updated_at",
        ]
    )

    submission = TimetableSubmission.objects.filter(
        resulting_timetable=timetable
    ).first()
    if submission is not None:
        submission.status = TimetableStatus.PUBLISHED
        submission.save(update_fields=["status", "updated_at"])

    _notify_published_timetable(
        timetable=timetable,
        previous_snapshot=previous_snapshot,
        change_note=change_note,
    )

    log_event(
        None,
        action="timetable.published",
        user=publisher,
        entity=timetable,
        summary=f"Published {timetable.section} timetable v{timetable.version}",
        metadata={"version": timetable.version, "entries": timetable.entries.count()},
    )
    return timetable


def _notify_published_timetable(*, timetable: Timetable, previous_snapshot, change_note: str) -> None:
    notify_class(
        class_room=timetable.class_room,
        section=timetable.section,
        category="TIMETABLE",
        title="Your class timetable has been updated.",
        body=(
            f"Timetable v{timetable.version} is now live"
            + (f", effective {timetable.effective_from:%d %B %Y}." if timetable.effective_from else ".")
        ),
        action_url="/timetable",
        action_label="View timetable",
        dedupe_suffix=f"v{timetable.version}",
    )

    if not previous_snapshot:
        return

    current = {
        (e.day_of_week, e.start_time): e.subject_id
        for e in timetable.entries.select_related("subject")
    }
    subject_names = {s.id: s.name for s in Subject.objects.filter(id__in=set(current.values()))}

    for (day, start), subject_id in current.items():
        previous_subject = previous_snapshot.get((day, start))
        if previous_subject == subject_id:
            continue
        subject_name = subject_names.get(subject_id, "A subject")
        if previous_subject is None:
            message = f"{subject_name} has been added to {Weekday.label_for(day)} at {start:%H:%M}."
        else:
            old_name = Subject.objects.filter(id=previous_subject).values_list("name", flat=True).first()
            message = (
                f"{subject_name} has moved to {Weekday.label_for(day)} at {start:%H:%M}."
                + (f" It previously replaced {old_name}." if old_name else "")
            )
        notify_class(
            class_room=timetable.class_room,
            section=timetable.section,
            category="TIMETABLE",
            title="Timetable change",
            body=message,
            action_url="/timetable",
            action_label="Open timetable",
            dedupe_suffix=f"v{timetable.version}:{day}:{start.isoformat()}",
        )


@transaction.atomic
def materialise_timetable_from_submission(
    *, submission: TimetableSubmission, publisher, change_note: str = ""
) -> Timetable:
    """Turns an approved structured submission into a versioned, publishable timetable."""

    if not submission.entries_payload:
        raise TelAPIException(
            "This submission has no structured entries. Review it manually before publishing."
        )

    class_room = submission.class_room
    section = submission.section
    academic_year = submission.academic_year
    offered = {
        o.subject.code.upper(): o
        for o in SubjectOffering.objects.filter(
            class_room=class_room, academic_year=academic_year, is_active=True
        ).select_related("subject", "teacher")
    }

    latest_version = (
        Timetable.objects.filter(
            class_room=class_room, section=section, academic_year=academic_year
        )
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
    )
    timetable = Timetable(
        class_room=class_room,
        section=section,
        academic_year=academic_year,
        version=(latest_version or 0) + 1,
        status=TimetableStatus.APPROVED,
        title=f"{class_room.name} — {section.name} weekly timetable",
        created_by=submission.submitted_by,
        approved_by=publisher,
        approved_at=timezone.now(),
        change_note=change_note or submission.change_note,
        source="CLASS_REPRESENTATIVE",
    )
    timetable.save()

    from django.utils.dateparse import parse_time

    entries = []
    for raw in submission.entries_payload:
        offering = offered[raw["subject_code"]]
        entries.append(
            TimetableEntry(
                timetable=timetable,
                day_of_week=raw["day"],
                start_time=parse_time(raw["start"]),
                end_time=parse_time(raw["end"]),
                subject=offering.subject,
                teacher=offering.teacher,
                room=raw.get("room") or section.room,
                campus=class_room.campus,
                note=raw.get("note", ""),
            )
        )
    TimetableEntry.objects.bulk_create(entries)

    submission.resulting_timetable = timetable
    submission.save(update_fields=["resulting_timetable", "updated_at"])
    return timetable
