"""
Staff dashboard aggregation for teachers and administrators.

The student dashboard in :mod:`core.dashboard` answers "what does this student
need today?". This module answers the two staff questions instead:

* a teacher — "what am I teaching, and what is waiting for me?"
* an administrator — "what is the state of the institution, and which queue
  needs me next?"

Two scoping rules are deliberate and security relevant:

* A teacher's payload is derived from ``SubjectOffering.teacher``. That is the
  durable class/subject mapping, unlike ``Paper.teacher`` / ``Assignment.teacher``
  which are ``SET_NULL`` and silently drop records whose teacher was cleared.
* An administrator's payload is institution wide. A teacher is never handed the
  aggregate — the per-teacher response contains only classes that teacher is
  actually assigned to.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import Role, StudentProfile
from academics.models import (
    AcademicYear,
    ClassRoom,
    Program,
    SubjectOffering,
    Timetable,
    TimetableEntry,
    TimetableStatus,
    TimetableSubmission,
    Weekday,
)
from assessment.models import Paper, PaperStatus, Result, ResultStatus
from core.models import AuditLog, Notification
from academics.selectors import days_until_period, next_period
from engagement.models import (
    ATTENDED_STATUSES,
    OPEN_REQUEST_STATUSES,
    AcademicEvent,
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    AttendanceRecord,
    Feedback,
    StudentRequest,
)

#: An administrator's "needs attention" threshold for a student whose attendance
#: over the trailing window has fallen below this percentage.
AT_RISK_ATTENDANCE = 75.0
#: Trailing window, in days, used for every attendance aggregate on this page.
ATTENDANCE_WINDOW_DAYS = 90
#: Assignment submissions that still need a human to look at them.
UNREVIEWED_SUBMISSION_STATUSES = [AssignmentStatus.SUBMITTED, AssignmentStatus.LATE]
#: Timetable submissions a reviewer has not yet resolved.
OPEN_TIMETABLE_STATUSES = [
    TimetableStatus.SUBMITTED,
    TimetableStatus.UNDER_REVIEW,
    TimetableStatus.CHANGES_REQUESTED,
]


def _iso(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _num(value):
    """Casts Decimal / None to a JSON-safe float."""
    return float(value) if value is not None else None


def _queue_item(obj, **extra) -> dict:
    return {"id": obj.pk, **extra}


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------


def build_teacher_dashboard(*, user) -> dict:
    now = timezone.localtime()
    greeting, _ = _greeting(now)

    profile = getattr(user, "teacher_profile", None)
    offerings = list(
        SubjectOffering.objects.filter(teacher=user, is_active=True)
        .select_related("subject", "class_room", "class_room__campus", "class_room__program", "section")
        .order_by("class_room__name", "section__name", "subject__name")
    )

    class_pairs = {(o.class_room_id, o.section_id) for o in offerings}
    class_ids = {cid for cid, _ in class_pairs}
    section_ids = {sid for _, sid in class_pairs if sid}

    teaching = _teaching_load(offerings, class_ids, section_ids)
    today, next_entry = _teacher_schedule(user, now)
    students_qs = _students_in(class_ids, section_ids)

    stats = {
        "classes": len(class_pairs),
        "subjects": len({o.subject_id for o in offerings}),
        "students": students_qs.count(),
        "papers": Paper.objects.filter(teacher=user, is_archived=False).count(),
        "unreviewed_submissions": _pending_submission_count(class_ids, section_ids),
        "timetable_queue": TimetableSubmission.objects.filter(
            status__in=OPEN_TIMETABLE_STATUSES
        )
        .filter(Q(class_room_id__in=class_ids))
        .count()
        if class_ids
        else 0,
        "open_requests": _open_request_count(class_ids),
    }

    return {
        "role": Role.TEACHER,
        "generated_at": now.isoformat(),
        "identity": {
            "greeting": greeting,
            "first_name": user.get_short_name(),
            "full_name": user.full_name,
            "email": user.email,
            "employee_code": profile.employee_code if profile else "",
            "designation": profile.designation if profile else "",
            "campus": profile.campus.name if profile and profile.campus else "",
        },
        "stats": stats,
        "today_classes": today,
        "next_class": next_entry,
        "teaching": teaching,
        "queues": {
            "unreviewed_submissions": _unreviewed_submissions(class_ids, section_ids),
            "timetable_submissions": _timetable_queue(class_ids),
            "open_requests": _open_requests(class_ids, limit=6),
        },
        "at_risk_students": _at_risk_students(students_qs, now),
        "unplaced_hint": _unplaced_hint(offerings),
        "notifications": {"unread": Notification.objects.visible_to(user).unread().count()},
    }


def _teaching_load(offerings, class_ids, section_ids) -> list[dict]:
    """One row per class the teacher owns, with its subject and cohort size."""

    by_class: dict[tuple, list] = {}
    for offering in offerings:
        by_class.setdefault((offering.class_room_id, offering.section_id), []).append(offering)

    rows = []
    for (class_id, section_id), group in by_class.items():
        cohort = StudentProfile.objects.filter(class_room_id=class_id, status=StudentProfile.Status.ACTIVE)
        if section_id:
            cohort = cohort.filter(section_id=section_id)
        rows.append(
            {
                "class_id": class_id,
                "section_id": section_id,
                "class_name": group[0].class_room.display_name,
                "section_name": group[0].section.name if group[0].section else "All sections",
                "campus": group[0].class_room.campus.name if group[0].class_room.campus else "",
                "subjects": [
                    {"id": o.subject_id, "name": o.subject.name, "color": o.subject.color_token}
                    for o in group
                ],
                "student_count": cohort.count(),
            }
        )
    rows.sort(key=lambda r: (r["class_name"], r["section_name"]))
    return rows


def _teacher_schedule(user, now) -> tuple[list[dict], dict | None]:
    """Today's periods and the next one, from published timetable entries."""

    entries = list(
        TimetableEntry.objects.filter(
            teacher=user,
            timetable__status=TimetableStatus.PUBLISHED,
        )
        .select_related("subject", "campus", "timetable__class_room", "section_override")
        .order_by("day_of_week", "start_time")
    )

    today = [
        _period_payload(e, now)
        for e in entries
        if e.day_of_week == now.weekday()
    ]
    upcoming = next_period(entries, now)
    if upcoming is None:
        return today, None

    target_date = now.date() + timedelta(days=days_until_period(upcoming, now))
    payload = _period_payload(upcoming, now)
    payload["is_today"] = upcoming.day_of_week == now.weekday()
    payload["date"] = target_date.isoformat()
    payload["day_label"] = Weekday.label_for(upcoming.day_of_week)
    return today, payload


def _period_payload(entry, now) -> dict:
    timetable = entry.timetable
    section = entry.section_override or timetable.section
    return {
        "id": entry.id,
        "subject": entry.subject.name,
        "subject_code": entry.subject.code,
        "subject_color": entry.subject.color_token,
        "class_name": timetable.class_room.display_name if timetable.class_room_id else "",
        "section_name": section.name if section else "All sections",
        "room": entry.room,
        "campus": entry.campus.name if entry.campus else "",
        "day": entry.day_of_week,
        "start": entry.start_time.isoformat(),
        "end": entry.end_time.isoformat(),
        "start_label": f"{entry.start_time:%I:%M %p}".lstrip("0"),
        "end_label": f"{entry.end_time:%I:%M %p}".lstrip("0"),
        "is_current": entry.start_time <= now.time() < entry.end_time,
        "is_past": entry.end_time <= now.time(),
    }


def _students_in(class_ids, set_of_section_ids) -> StudentProfile.QuerySet:
    if not class_ids:
        return StudentProfile.objects.none()
    qs = StudentProfile.objects.filter(
        class_room_id__in=class_ids, status=StudentProfile.Status.ACTIVE
    ).select_related("class_room", "section", "user")
    return qs


def _pending_submission_count(class_ids, section_ids) -> int:
    if not class_ids:
        return 0
    return (
        AssignmentSubmission.objects.filter(
            status__in=UNREVIEWED_SUBMISSION_STATUSES,
            assignment__class_room_id__in=class_ids,
        )
        .filter(
            Q(assignment__section_id__in=section_ids)
            if section_ids
            else Q(assignment__section__isnull=True)
        )
        .count()
    )


def _unreviewed_submissions(class_ids, section_ids, limit: int = 6) -> list[dict]:
    if not class_ids:
        return []
    qs = (
        AssignmentSubmission.objects.filter(
            status__in=UNREVIEWED_SUBMISSION_STATUSES,
            assignment__class_room_id__in=class_ids,
        )
        .filter(
            Q(assignment__section_id__in=section_ids)
            if section_ids
            else Q(assignment__section__isnull=True)
        )
        .select_related("student", "student__user", "assignment", "assignment__subject")
        .order_by("submitted_at")
    )
    return [
        {
            "id": row.pk,
            "student_name": row.student.user.full_name if row.student_id else "",
            "student_code": row.student.student_code if row.student_id else "",
            "assignment_title": row.assignment.title,
            "subject": row.assignment.subject.name,
            "subject_color": row.assignment.subject.color_token,
            "status": row.status,
            "submitted_at": _iso(row.submitted_at),
        }
        for row in qs[:limit]
    ]


def _timetable_queue(class_ids, limit: int = 6) -> list[dict]:
    if not class_ids:
        return []
    qs = (
        TimetableSubmission.objects.filter(
            status__in=OPEN_TIMETABLE_STATUSES, class_room_id__in=class_ids
        )
        .select_related("class_room", "section", "submitted_by")
        .order_by("created_at")
    )
    return [
        {
            "id": row.pk,
            "class_name": row.class_room.display_name if row.class_room_id else "",
            "section_name": row.section.name if row.section_id else "All sections",
            "submitted_by": row.submitted_by.full_name if row.submitted_by else "",
            "summary": row.summary,
            "status": row.status,
            "created_at": _iso(row.created_at),
        }
        for row in qs[:limit]
    ]


def _open_request_count(class_ids) -> int:
    if not class_ids:
        return 0
    return StudentRequest.objects.filter(
        status__in=OPEN_REQUEST_STATUSES,
        student__class_room_id__in=class_ids,
    ).count()


def _open_requests(class_ids, limit: int = 6) -> list[dict]:
    if not class_ids:
        return []
    qs = (
        StudentRequest.objects.filter(
            status__in=OPEN_REQUEST_STATUSES,
            student__class_room_id__in=class_ids,
        )
        .select_related("student", "student__user")
        .order_by("created_at")
    )
    return [
        {
            "id": row.pk,
            "ticket_id": row.ticket_id,
            "student_name": row.student.user.full_name if row.student_id else "",
            "request_type": row.request_type,
            "request_type_label": row.get_request_type_display(),
            "subject_line": row.subject_line,
            "status": row.status,
            "created_at": _iso(row.created_at),
        }
        for row in qs[:limit]
    ]


def _at_risk_students(students_qs, now, limit: int = 6) -> list[dict]:
    """Students in the teacher's classes whose trailing attendance is low."""

    student_ids = list(students_qs.values_list("pk", flat=True))
    if not student_ids:
        return []

    since = now.date() - timedelta(days=ATTENDANCE_WINDOW_DAYS)
    totals = {
        row["student_id"]: row
        for row in AttendanceRecord.objects.filter(
            student_id__in=student_ids, date__gte=since
        )
        .values("student_id")
        .annotate(
            total=Count("id"),
            attended=Count("id", filter=Q(status__in=ATTENDED_STATUSES)),
        )
    }

    at_risk = []
    for profile in students_qs:
        row = totals.get(profile.pk)
        if not row or not row["total"]:
            continue
        percentage = round(row["attended"] * 100.0 / row["total"], 1)
        if percentage >= AT_RISK_ATTENDANCE:
            continue
        at_risk.append(
            {
                "id": profile.pk,
                "name": profile.user.full_name if profile.user_id else "",
                "student_code": profile.student_code,
                "class_name": profile.class_room.display_name if profile.class_room_id else "",
                "section_name": profile.section.name if profile.section_id else "",
                "percentage": percentage,
                "sessions": row["total"],
            }
        )
    at_risk.sort(key=lambda r: r["percentage"])
    return at_risk[:limit]


def _unplaced_hint(offerings) -> str:
    if offerings:
        return ""
    return (
        "You are not assigned to any class yet, so there is nothing to show. "
        "An administrator needs to set your subject offerings."
    )


# ---------------------------------------------------------------------------
# Administrator
# ---------------------------------------------------------------------------


def build_admin_dashboard(*, user) -> dict:
    now = timezone.localtime()
    greeting, _ = _greeting(now)
    current_year = AcademicYear.objects.filter(is_current=True).first()

    active_students = StudentProfile.objects.filter(status=StudentProfile.Status.ACTIVE)
    active_students_qs = active_students.select_related("campus", "program")

    stats = {
        "students": active_students.count(),
        "teachers": _teacher_count(),
        "classes": ClassRoom.objects.filter(is_active=True).count(),
        "programs": Program.objects.filter(is_active=True).count(),
        "unplaced_students": _unplaced_count(),
        "papers_draft": Paper.objects.filter(status=PaperStatus.DRAFT, is_archived=False).count(),
        "papers_unverified": Paper.objects.filter(status=PaperStatus.COMPLETED, is_archived=False).count(),
        "results_unpublished": Result.objects.filter(
            status__in=[ResultStatus.DRAFT, ResultStatus.SUBMITTED, ResultStatus.VERIFIED],
            is_revoked=False,
        ).count(),
        "timetable_queue": TimetableSubmission.objects.filter(
            status__in=OPEN_TIMETABLE_STATUSES
        ).count(),
        "open_requests": StudentRequest.objects.filter(status__in=OPEN_REQUEST_STATUSES).count(),
        "new_feedback": Feedback.objects.filter(status="NEW").count(),
    }

    return {
        "role": Role.ADMIN,
        "generated_at": now.isoformat(),
        "identity": {
            "greeting": greeting,
            "first_name": user.get_short_name(),
            "full_name": user.full_name,
            "email": user.email,
            "designation": "Administrator",
            "campus": "All campuses",
        },
        "academic_year": {
            "id": current_year.pk if current_year else None,
            "label": current_year.label if current_year else "",
            "is_current": current_year is not None,
        },
        "stats": stats,
        "enrolment": {
            "by_campus": _enrolment_by("campus", active_students_qs, limit=8),
            "by_program": _enrolment_by("program", active_students_qs, limit=8),
        },
        "queues": {
            "papers_awaiting_verification": _paper_queue(limit=6),
            "results_awaiting_publication": _result_queue(limit=6),
            "timetable_submissions": _admin_timetable_queue(limit=6),
            "open_requests": _admin_request_queue(limit=6),
            "unplaced_students": _unplaced_students(limit=6),
        },
        "upcoming_events": _upcoming_events(limit=6),
        "recent_activity": _recent_activity(limit=8),
        "notifications": {"unread": Notification.objects.visible_to(user).unread().count()},
    }


def _teacher_count() -> int:
    from accounts.models import TeacherProfile

    return TeacherProfile.objects.filter(user__is_active=True).count()


def _unplaced_count() -> int:
    return (
        StudentProfile.objects.filter(status=StudentProfile.Status.ACTIVE)
        .filter(
            Q(class_room__isnull=True)
            | Q(section__isnull=True)
            | Q(academic_year__isnull=True)
            | Q(campus__isnull=True)
            | Q(program__isnull=True)
        )
        .count()
    )


def _enrolment_by(field, qs, limit: int = 8) -> list[dict]:
    rows = (
        qs.values(f"{field}__id", f"{field}__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )
    out = []
    for row in rows:
        group_id = row.get(f"{field}__id")
        if group_id is None:
            continue
        out.append({"id": group_id, "name": row[f"{field}__name"], "total": row["total"]})
    return out


def _paper_queue(limit: int = 6) -> list[dict]:
    qs = (
        Paper.objects.filter(status=PaperStatus.COMPLETED, is_archived=False)
        .select_related("subject", "class_room", "teacher")
        .order_by("created_at")
    )
    return [
        {
            "id": row.pk,
            "title": row.title,
            "subject": row.subject.name,
            "subject_color": row.subject.color_token,
            "class_name": row.class_room.display_name if row.class_room_id else "",
            "teacher": row.teacher.full_name if row.teacher_id else "",
            "total_marks": _num(row.total_marks),
            "created_at": _iso(row.created_at),
        }
        for row in qs[:limit]
    ]


def _result_queue(limit: int = 6) -> list[dict]:
    qs = (
        Result.objects.filter(
            status__in=[ResultStatus.DRAFT, ResultStatus.SUBMITTED, ResultStatus.VERIFIED],
            is_revoked=False,
        )
        .select_related("student", "student__user", "subject")
        .order_by("assessment_date")
    )
    return [
        {
            "id": row.pk,
            "student_name": row.student.user.full_name if row.student_id else "",
            "assessment_name": row.assessment_name,
            "subject": row.subject.name,
            "subject_color": row.subject.color_token,
            "percentage": _num(row.percentage),
            "status": row.status,
            "assessment_date": _iso(row.assessment_date),
        }
        for row in qs[:limit]
    ]


def _admin_timetable_queue(limit: int = 6) -> list[dict]:
    qs = (
        TimetableSubmission.objects.filter(status__in=OPEN_TIMETABLE_STATUSES)
        .select_related("class_room", "section", "submitted_by")
        .order_by("created_at")
    )
    return [
        {
            "id": row.pk,
            "class_name": row.class_room.display_name if row.class_room_id else "",
            "section_name": row.section.name if row.section_id else "All sections",
            "submitted_by": row.submitted_by.full_name if row.submitted_by else "",
            "summary": row.summary,
            "status": row.status,
            "created_at": _iso(row.created_at),
        }
        for row in qs[:limit]
    ]


def _admin_request_queue(limit: int = 6) -> list[dict]:
    qs = (
        StudentRequest.objects.filter(status__in=OPEN_REQUEST_STATUSES)
        .select_related("student", "student__user", "student__class_room")
        .order_by("created_at")
    )
    return [
        {
            "id": row.pk,
            "ticket_id": row.ticket_id,
            "student_name": row.student.user.full_name if row.student_id else "",
            "class_name": row.student.class_room.display_name
            if row.student_id and row.student.class_room_id
            else "",
            "request_type": row.request_type,
            "request_type_label": row.get_request_type_display(),
            "subject_line": row.subject_line,
            "status": row.status,
            "created_at": _iso(row.created_at),
        }
        for row in qs[:limit]
    ]


def _unplaced_students(limit: int = 6) -> list[dict]:
    qs = (
        StudentProfile.objects.filter(status=StudentProfile.Status.ACTIVE)
        .filter(
            Q(class_room__isnull=True)
            | Q(section__isnull=True)
            | Q(academic_year__isnull=True)
            | Q(campus__isnull=True)
            | Q(program__isnull=True)
        )
        .select_related("user", "campus", "program")
        .order_by("student_code")
    )
    missing = []
    for row in qs[:limit]:
        gaps = [
            label
            for label, value in (
                ("campus", row.campus_id),
                ("program", row.program_id),
                ("class", row.class_room_id),
                ("section", row.section_id),
                ("academic year", row.academic_year_id),
            )
            if not value
        ]
        missing.append(
            {
                "id": row.pk,
                "name": row.user.full_name if row.user_id else "",
                "student_code": row.student_code,
                "missing": ", ".join(gaps),
            }
        )
    return missing


def _upcoming_events(limit: int = 6) -> list[dict]:
    window = timezone.localtime() + timedelta(days=45)
    qs = (
        AcademicEvent.objects.filter(starts_at__gte=timezone.localtime() - timedelta(hours=12))
        .filter(starts_at__lte=window)
        .select_related("subject")
        .order_by("starts_at")[:limit]
    )
    return [
        {
            "id": row.pk,
            "title": row.title,
            "event_type_label": row.get_event_type_display(),
            "starts_at": _iso(row.starts_at),
            "is_all_day": row.is_all_day,
            "subject_color": row.subject.color_token if row.subject_id else "sage",
        }
        for row in qs
    ]


def _recent_activity(limit: int = 8) -> list[dict]:
    qs = AuditLog.objects.select_related("actor").order_by("-created_at")[:limit]
    return [
        {
            "id": row.pk,
            "action": row.action,
            "summary": row.summary,
            "actor": row.actor.full_name if row.actor_id else "System",
            "actor_role": row.actor_role,
            "created_at": _iso(row.created_at),
        }
        for row in qs
    ]


def _greeting(now) -> tuple[str, str]:
    hour = now.hour
    if hour < 12:
        return "Good morning", "day"
    if hour < 17:
        return "Good afternoon", "day"
    return "Good evening", "evening"
