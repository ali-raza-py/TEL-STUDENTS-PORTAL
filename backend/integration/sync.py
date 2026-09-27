from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from accounts.models import StudentProfile, User
from academics.models import AcademicYear, Campus, ClassRoom, Program, Section, Subject, Timetable, TimetableEntry, TimetableStatus, Weekday
from assessment.models import Paper, PaperStatus, Result, ResultStatus
from engagement.models import AcademicEvent, Announcement, AttendanceRecord, AttendanceStatus, Resource
from integration.adapters import FieldMapper, SyncOutcome, get_adapter, parse_date

logger = logging.getLogger("telportal.integration")


def sync_all(*, adapter=None, entities: list[str] | None = None, actor=None) -> dict[str, SyncOutcome]:
    """
    Pulls authorised data from TEL core into the portal's local mirror.

    The sync is idempotent: it matches on TEL's own identifiers so running it
    twice will not duplicate anything.
    """

    adapter = adapter or get_adapter()
    mapper = FieldMapper()
    entities = entities or [
        "student", "subject", "class", "timetable", "attendance", "result", "paper",
        "announcement", "resource", "event",
    ]
    outcomes: dict[str, SyncOutcome] = {}
    for entity in entities:
        handler = _HANDLERS.get(entity)
        if handler is None:
            continue
        outcome = SyncOutcome(entity=entity)
        try:
            rows = list(adapter.fetch(entity))
        except Exception as exc:  # noqa: BLE001 - one entity must not stop the rest
            logger.warning("Fetch failed for %s: %s", entity, exc)
            outcome.errors.append(f"{exc.__class__.__name__}: {exc}")
            outcomes[entity] = outcome
            continue
        for raw in rows:
            try:
                handler(mapper.map(entity, raw) if raw else {}, outcome, actor=actor)
            except Exception as exc:  # noqa: BLE001
                outcome.errors.append(f"{exc.__class__.__name__}: {exc}")
                outcome.skipped += 1
        outcomes[entity] = outcome
    return outcomes


def _upsert_campus(code: str, name: str) -> Campus:
    obj, _ = Campus.objects.get_or_create(code=code[:16], defaults={"name": name[:120]})
    return obj


def _upsert_program(code: str, name: str) -> Program:
    obj, _ = Program.objects.get_or_create(code=code[:16], defaults={"name": name[:120]})
    return obj


def _upsert_subject(code: str, name: str, program: Program | None) -> Subject:
    defaults = {"name": name[:140]}
    if program:
        defaults["program"] = program
    obj, _ = Subject.objects.get_or_create(code=code[:24], defaults=defaults)
    return obj


def _handle_subject(row: dict, outcome: SyncOutcome, actor=None) -> None:
    code = (row.get("code") or "").strip()
    name = (row.get("name") or "").strip()
    if not code or not name:
        outcome.skipped += 1
        return
    program = None
    if row.get("program"):
        program = Program.objects.filter(code=str(row["program"])).first() or Program.objects.filter(
            name=str(row["program"])
        ).first()
    if program is None:
        program = Program.objects.first()
    if program is None:
        outcome.skipped += 1
        return
    _, created = Subject.objects.get_or_create(code=code[:24], defaults={"name": name[:140], "program": program})
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_student(row: dict, outcome: SyncOutcome, actor=None) -> None:
    code = (row.get("student_code") or row.get("id") or "").strip()
    email = (row.get("email") or "").strip().lower()
    if not code or not email:
        outcome.skipped += 1
        return
    with transaction.atomic():
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": row.get("full_name") or email.split("@")[0]},
        )
        if user_created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        if row.get("full_name") and user.full_name != row["full_name"]:
            user.full_name = row["full_name"][:160]
            user.save(update_fields=["full_name"])

        defaults = {
            "roll_number": str(row.get("roll_number") or "")[:32],
            "last_synced_from_tel": timezone.now(),
        }
        for key in ("campus", "program", "class_room", "section", "academic_year"):
            if row.get(key):
                model = {
                    "campus": Campus, "program": Program,
                    "class_room": ClassRoom, "section": Section, "academic_year": AcademicYear,
                }[key]
                label = str(row[key])
                match = model.objects.filter(code=label).first() or model.objects.filter(name=label).first()
                if match is not None:
                    defaults[key] = match

        _, created = StudentProfile.objects.update_or_create(
            student_code=code[:32], defaults={"user": user, **defaults}
        )
        outcome.created += int(created)
        outcome.updated += int(not created)


def _handle_attendance(row: dict, outcome: SyncOutcome, actor=None) -> None:
    profile = StudentProfile.objects.filter(
        student_code=str(row.get("student_code") or "")
    ).first()
    subject_code = str(row.get("subject") or "")
    subject = Subject.objects.filter(code=subject_code).first() or Subject.objects.filter(
        name=subject_code
    ).first()
    day = parse_date(row.get("date"))
    if profile is None or subject is None or day is None or profile.class_room is None:
        outcome.skipped += 1
        return
    _, created = AttendanceRecord.objects.update_or_create(
        student=profile,
        subject=subject,
        date=day,
        defaults={
            "class_room": profile.class_room,
            "status": _attendance_status(row),
            "period_label": str(row.get("period_label") or "")[:32],
            "source": "TEL_CORE",
        },
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _attendance_status(row: dict) -> str:
    raw = str(row.get("status") or "").lower()
    mapping = {
        "p": AttendanceStatus.PRESENT, "present": AttendanceStatus.PRESENT, "1": AttendanceStatus.PRESENT,
        "a": AttendanceStatus.ABSENT, "absent": AttendanceStatus.ABSENT, "0": AttendanceStatus.ABSENT,
        "l": AttendanceStatus.LATE, "late": AttendanceStatus.LATE,
        "e": AttendanceStatus.EXCUSED, "excused": AttendanceStatus.EXCUSED,
        "od": AttendanceStatus.ON_DUTY, "on_duty": AttendanceStatus.ON_DUTY,
    }
    return mapping.get(raw, AttendanceStatus.PRESENT)


def _handle_result(row: dict, outcome: SyncOutcome, actor=None) -> None:
    from assessment.services import grade_for

    profile = StudentProfile.objects.filter(
        student_code=str(row.get("student_code") or "")
    ).first()
    subject = Subject.objects.filter(code=str(row.get("subject") or "")).first()
    if profile is None or subject is None:
        outcome.skipped += 1
        return
    total = float(row.get("total_marks") or 0)
    obtained = float(row.get("obtained_marks") or 0)
    if total <= 0:
        outcome.skipped += 1
        return

    percentage = round(obtained / total * 100, 2)
    _, created = Result.objects.update_or_create(
        student=profile,
        assessment_name=str(row.get("assessment_name") or "Assessment")[:200],
        assessment_type=str(row.get("assessment_type") or "MONTHLY_TEST"),
        defaults={
            "subject": subject,
            "assessment_date": parse_date(row.get("assessment_date")) or timezone.localdate(),
            "total_marks": total,
            "obtained_marks": obtained,
            "percentage": percentage,
            "grade": grade_for(percentage),
            "status": ResultStatus.PUBLISHED,
            "published_at": timezone.now(),
            "last_synced_from_tel": timezone.now(),
        },
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_paper(row: dict, outcome: SyncOutcome, actor=None) -> None:
    external_ref = str(row.get("external_ref") or row.get("id") or "")[:120]
    if not external_ref:
        outcome.skipped += 1
        return
    subject = Subject.objects.filter(code=str(row.get("subject") or "")).first()
    class_room = ClassRoom.objects.filter(code=str(row.get("class") or "")).first()
    if subject is None or class_room is None:
        outcome.skipped += 1
        return
    _, created = Paper.objects.update_or_create(
        external_ref=external_ref,
        defaults={
            "title": str(row.get("title") or "Paper")[:200],
            "subject": subject,
            "class_room": class_room,
            "campus": class_room.campus,
            "academic_year": class_room.academic_year,
            "exam_type": str(row.get("exam_type") or "MONTHLY_TEST"),
            "total_marks": int(row.get("total_marks") or 50),
            "exam_date": parse_date(row.get("exam_date")),
            "status": PaperStatus.PUBLISHED,
            "published_at": timezone.now(),
            "source": Paper.Source.TEL_CORE,
            "last_synced_from_tel": timezone.now(),
        },
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_announcement(row: dict, outcome: SyncOutcome, actor=None) -> None:
    title = (row.get("title") or "").strip()
    body = (row.get("body") or "").strip()
    if not title or not body:
        outcome.skipped += 1
        return
    _, created = Announcement.objects.get_or_create(
        title=title[:200],
        defaults={
            "body": body,
            "audience": str(row.get("audience") or "ALL_STUDENTS").upper(),
            "published_at": timezone.now(),
        },
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_resource(row: dict, outcome: SyncOutcome, actor=None) -> None:
    title = (row.get("title") or "").strip()
    if not title:
        outcome.skipped += 1
        return
    subject = Subject.objects.filter(code=str(row.get("subject") or "")).first()
    _, created = Resource.objects.get_or_create(
        title=title[:200],
        chapter=str(row.get("chapter") or "")[:140],
        defaults={"subject": subject, "description": str(row.get("description") or "")},
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_event(row: dict, outcome: SyncOutcome, actor=None) -> None:
    title = (row.get("title") or "").strip()
    starts_at = row.get("starts_at")
    if not title or not starts_at:
        outcome.skipped += 1
        return
    from django.utils.dateparse import parse_datetime

    parsed = parse_datetime(str(starts_at))
    if parsed is None:
        outcome.skipped += 1
        return
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    _, created = AcademicEvent.objects.get_or_create(
        title=title[:200], starts_at=parsed,
        defaults={"event_type": str(row.get("event_type") or "TEL_EVENT").upper()},
    )
    outcome.created += int(created)
    outcome.updated += int(not created)


def _handle_timetable(row: dict, outcome: SyncOutcome, actor=None) -> None:
    class_room = ClassRoom.objects.filter(code=str(row.get("class") or "")).first()
    if class_room is None:
        outcome.skipped += 1
        return
    section = Section.objects.filter(pk=row.get("section"), class_room=class_room).first()
    version = (
        Timetable.objects.filter(class_room=class_room, section=section, academic_year=class_room.academic_year)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    timetable = Timetable.objects.create(
        class_room=class_room, section=section, academic_year=class_room.academic_year,
        version=version, status=TimetableStatus.PUBLISHED, source="TEL_CORE",
        published_at=timezone.now(),
    )
    from django.utils.dateparse import parse_time

    entries = row.get("entries") or []
    for raw in entries:
        subject = Subject.objects.filter(code=str(raw.get("subject") or "")).first()
        if subject is None:
            continue
        day = raw.get("day_of_week", raw.get("day"))
        if isinstance(day, str):
            try:
                day = Weekday[day.upper()].value
            except KeyError:
                continue
        if day is None or not (0 <= int(day) <= 6):
            continue
        TimetableEntry.objects.create(
            timetable=timetable,
            day_of_week=int(day),
            start_time=parse_time(str(raw.get("start_time") or raw.get("start"))),
            end_time=parse_time(str(raw.get("end_time") or raw.get("end"))),
            subject=subject,
            room=str(raw.get("room") or "")[:64],
            campus=class_room.campus,
        )
    outcome.created += 1


_HANDLERS = {
    "subject": _handle_subject,
    "student": _handle_student,
    "attendance": _handle_attendance,
    "result": _handle_result,
    "paper": _handle_paper,
    "announcement": _handle_announcement,
    "resource": _handle_resource,
    "event": _handle_event,
    "timetable": _handle_timetable,
}


def prune_stale_notifications(days: int = 180) -> int:
    from core.notifications import prune_old_notifications

    return prune_old_notifications(days)


def run_scheduled_sync(actor=None) -> dict[str, SyncOutcome]:
    """Entry point used by the periodic management command."""

    from django.conf import settings

    if not settings.TEL_SYNC_ENABLED:
        return {}
    return sync_all(actor=actor)
