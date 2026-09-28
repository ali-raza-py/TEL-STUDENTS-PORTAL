"""
Dashboard aggregation.

The dashboard is a single endpoint that answers "what does this student need to
know today?". Every field is derived from the database; where TEL has not
published the underlying record the response carries an explicit empty shape
with a message, never a placeholder number.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from academics.models import Timetable, TimetableStatus, Weekday
from academics.selectors import days_until_period, next_period
from assessment import analytics
from assessment.models import Paper, PaperStatus, PracticeAttempt
from engagement import selectors as engagement_selectors
from engagement.models import AcademicEvent, Announcement, Assignment
from core.models import Notification, NotificationState


def _greeting(now) -> tuple[str, str]:
    hour = now.hour
    if hour < 12:
        return "Good morning", "day"
    if hour < 17:
        return "Good afternoon", "day"
    return "Good evening", "evening"


def build_dashboard(*, user, scope) -> dict:
    now = timezone.localtime()
    profile = scope.profile
    greeting, _ = _greeting(now)

    identity = {
        "greeting": greeting,
        "first_name": user.get_short_name(),
        "full_name": user.full_name,
        "student_code": profile.student_code,
        "campus": profile.campus.name if profile.campus else "",
        "program": profile.program.name if profile.program else "",
        "class_name": profile.class_room.name if profile.class_room else "",
        "class_display": profile.class_label(),
        "section": profile.section.name if profile.section else "",
        "academic_year": profile.academic_year.label if profile.academic_year else "",
        "profile_photo_url": None,
    }

    timetable_qs = Timetable.objects.filter(
        class_room_id=scope.class_id,
        section_id=scope.section_id,
        academic_year_id=scope.academic_year_id,
        status=TimetableStatus.PUBLISHED,
    ).first()

    next_class = None
    today_classes: list[dict] = []
    if timetable_qs is not None:
        entries = list(
            timetable_qs.entries.select_related("subject", "teacher", "campus").order_by(
                "day_of_week", "start_time"
            )
        )
        today_classes = [
            _class_payload(entry, now, Weekday.label_for(now.weekday()))
            for entry in entries
            if entry.day_of_week == now.weekday()
        ]
        upcoming = next_period(entries, now)
        if upcoming is not None:
            target_date = now.date() + timedelta(days=days_until_period(upcoming, now))
            next_class = {
                **_class_payload(upcoming, now, Weekday.label_for(upcoming.day_of_week)),
                "is_today": upcoming.day_of_week == now.weekday(),
                "date": target_date.isoformat(),
                "starts_in_minutes": _minutes_until(now, target_date, upcoming.start_time),
            }

    attendance = engagement_selectors.attendance_summary(profile)
    subjects = analytics.subject_performance(profile)
    weak = analytics.detect_weak_subjects(profile)

    recent_result = None
    latest_result = None
    from assessment.models import Result

    latest_result = (
        Result.objects.visible_to_students()
        .filter(student=profile)
        .select_related("subject")
        .order_by("-assessment_date", "-created_at")
        .first()
    )
    if latest_result is not None:
        from assessment.practice import grade_for

        recent_result = {
            "assessment_name": latest_result.assessment_name,
            "subject": latest_result.subject.name,
            "subject_code": latest_result.subject.code,
            "subject_color": latest_result.subject.color_token,
            "obtained_marks": float(latest_result.obtained_marks),
            "total_marks": float(latest_result.total_marks),
            "percentage": float(latest_result.percentage),
            "grade": latest_result.grade or grade_for(float(latest_result.percentage)),
            "date": latest_result.assessment_date.isoformat(),
        }

    papers_qs = (
        Paper.objects.visible_to_students()
        .filter(class_room_id=scope.class_id, academic_year_id=scope.academic_year_id)
        .filter(Q(section_id=scope.section_id) | Q(section__isnull=True))
        .select_related("subject", "class_room", "section", "campus", "academic_year")
    )
    practice_papers = list(
        papers_qs.filter(status=PaperStatus.PRACTICE_AVAILABLE)
        .annotate(question_count=Count("questions", distinct=True))
        .order_by("-exam_date")[:4]
    )
    from assessment.serializers import PaperListSerializer

    practice_payload = PaperListSerializer(
        practice_papers, many=True, context={"request": None, "attempts_by_paper": {}}
    ).data

    attempts_qs = PracticeAttempt.objects.filter(student=profile, status__in=["SUBMITTED", "GRADED"])
    practice_stats = {
        "attempts": attempts_qs.count(),
        "best_percentage": (
            round(
                float(
                    attempts_qs.order_by("-percentage")
                    .values_list("percentage", flat=True)
                    .first()
                    or 0
                ),
                1,
            )
            if attempts_qs.exists()
            else None
        ),
    }

    upcoming_test = _upcoming_test(papers_qs, assignments_due=None, now=now)
    due_assignments = _due_assignments(scope, now)

    announcements = _announcements(profile, now)
    events = _events(scope, now)

    attendance_summary = {
        "available": attendance["available"],
        "message": attendance.get("message", ""),
        "overall_percentage": attendance.get("overall_percentage"),
        "target_percentage": settings.TEL_ATTENDANCE_TARGET,
        "meets_target": (
            attendance.get("overall_percentage") is not None
            and attendance["overall_percentage"] >= settings.TEL_ATTENDANCE_TARGET
        ),
        "lowest_subject": attendance.get("lowest_subject"),
        "monthly_trend": attendance.get("monthly_trend", [])[-6:],
    }

    return {
        "generated_at": now.isoformat(),
        "identity": identity,
        "timetable": {
            "published": timetable_qs is not None,
            "version": timetable_qs.version if timetable_qs else None,
            "published_at": timetable_qs.published_at if timetable_qs else None,
            "message": "" if timetable_qs else "Your class timetable has not been published yet.",
        },
        "next_class": next_class,
        "today_classes": today_classes,
        "upcoming_test": upcoming_test,
        "due_assignments": due_assignments,
        "attendance": attendance_summary,
        "performance": {
            "available": bool(subjects),
            "message": "" if subjects else "No published results yet.",
            "overall_average": analytics.overall_average(profile),
            "subjects": [analytics.asdict_row(s) for s in subjects],
        },
        "recent_result": recent_result,
        "practice": {
            "available_papers": papers_qs.filter(status=PaperStatus.PRACTICE_AVAILABLE).count(),
            "papers": practice_payload,
            **practice_stats,
        },
        "weak_subjects": [analytics.asdict_row(w) for w in weak],
        "announcements": announcements,
        "events": events,
        "notifications": {
            "unread": Notification.objects.visible_to(user).unread().count(),
        },
        "thresholds": {
            "weak_subject_score": settings.TEL_WEAK_SUBJECT_SCORE,
            "attendance_target": settings.TEL_ATTENDANCE_TARGET,
        },
    }


def _class_payload(entry, now, day_label: str) -> dict:
    return {
        "id": entry.id,
        "day": entry.day_of_week,
        "day_label": day_label,
        "subject": entry.subject.name,
        "subject_code": entry.subject.code,
        "subject_color": entry.subject.color_token,
        "teacher": entry.teacher.full_name if entry.teacher else "",
        "room": entry.room,
        "campus": entry.campus.name if entry.campus else "",
        "start": entry.start_time.isoformat(),
        "end": entry.end_time.isoformat(),
        "start_label": f"{entry.start_time:%I:%M %p}".lstrip("0"),
        "end_label": f"{entry.end_time:%I:%M %p}".lstrip("0"),
        "is_current": entry.start_time <= now.time() < entry.end_time,
        "is_past": entry.end_time <= now.time(),
        "note": entry.note,
    }


def _minutes_until(now, target_date, target_time) -> int:
    """Whole minutes from ``now`` until ``target_time`` on ``target_date``."""

    target = datetime.combine(target_date, target_time)
    if timezone.is_naive(target):
        target = timezone.make_aware(target, now.tzinfo)
    return max(0, int((target - now).total_seconds() // 60))


def _upcoming_test(papers_qs, *, assignments_due, now) -> dict | None:
    from assessment.models import ExamType

    soon = now + timedelta(days=14)
    upcoming = (
        papers_qs.filter(
            exam_date__isnull=False,
            exam_date__gte=now.date(),
            exam_date__lte=soon.date(),
        )
        .exclude(exam_type=ExamType.PRACTICE)
        .select_related("subject")
        .order_by("exam_date")
        .first()
    )
    if upcoming is None:
        return {
            "available": False,
            "message": "No test scheduled in the next two weeks.",
        }
    days = (upcoming.exam_date - now.date()).days
    return {
        "available": True,
        "paper_id": upcoming.pk,
        "title": upcoming.title,
        "subject": upcoming.subject.name,
        "subject_code": upcoming.subject.code,
        "subject_color": upcoming.subject.color_token,
        "date": upcoming.exam_date.isoformat(),
        "total_marks": upcoming.total_marks,
        "duration_minutes": upcoming.duration_minutes,
        "days_away": days,
        "relative": "Today" if days == 0 else "Tomorrow" if days == 1 else f"In {days} days",
    }


def _due_assignments(scope, now) -> dict:
    horizon = now + timedelta(days=14)
    qs = Assignment.objects.filter(
        is_published=True, class_room_id=scope.class_id, due_on__gte=now.date(), due_on__lte=horizon
    ).filter(Q(section_id=scope.section_id) | Q(section__isnull=True))
    count = qs.count()
    nearest = qs.select_related("subject").order_by("due_on").first()
    if count == 0:
        return {"available": False, "message": "No assignments due in the next two weeks.", "count": 0}
    return {
        "available": True,
        "count": count,
        "next": {
            "id": nearest.pk,
            "title": nearest.title,
            "subject": nearest.subject.name,
            "subject_color": nearest.subject.color_token,
            "due_on": nearest.due_on.isoformat(),
            "days_remaining": (nearest.due_on - now.date()).days,
        },
    }


def _announcements(profile, now, limit: int = 4) -> list[dict]:
    qs = (
        Announcement.objects.filter(is_published=True, published_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exclude(audience="STAFF")
        .filter(
            Q(audience="ALL_STUDENTS")
            | Q(audience="CAMPUS", campus_id=profile.campus_id)
            | Q(audience="PROGRAM", program_id=profile.program_id)
            | Q(audience="CLASS", class_room_id=profile.class_room_id)
            | Q(audience="SECTION", section_id=profile.section_id)
            | Q(audience="ACADEMIC_YEAR", academic_year_id=profile.academic_year_id)
        )
        .select_related("campus", "class_room", "section", "created_by")
        .order_by("-is_pinned", "-published_at")[:limit]
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "body": row.body[:280],
            "audience_label": row.get_audience_display(),
            "scope": _scope_label(row),
            "author": row.created_by.full_name if row.created_by else "TEL",
            "published_at": row.published_at,
            "is_pinned": row.is_pinned,
        }
        for row in qs
    ]


def _scope_label(row: Announcement) -> str:
    if row.section:
        return f"{row.section.class_room.name} — {row.section.name}"
    if row.class_room:
        return row.class_room.name
    if row.program:
        return row.program.name
    if row.campus:
        return row.campus.name
    return "All TEL students"


def _events(scope, now, limit: int = 5) -> list[dict]:
    window = now + timedelta(days=45)
    qs = (
        AcademicEvent.objects.filter(starts_at__gte=now, starts_at__lte=window)
        .filter(Q(campus_id__isnull=True) | Q(campus_id=scope.campus_id))
        .filter(Q(class_room_id__isnull=True) | Q(class_room_id=scope.class_id))
        .filter(Q(section_id__isnull=True) | Q(section_id=scope.section_id))
        .select_related("subject")
        .order_by("starts_at")[:limit]
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "event_type": row.event_type,
            "event_type_label": row.get_event_type_display(),
            "starts_at": row.starts_at,
            "is_all_day": row.is_all_day,
            "subject_color": row.subject.color_token if row.subject else "sage",
        }
        for row in qs
    ]


def unread_notifications(user) -> int:
    return Notification.objects.visible_to(user).filter(state=NotificationState.UNREAD).count()
