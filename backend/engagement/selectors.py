from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from engagement.models import ATTENDED_STATUSES, AttendanceRecord, AttendanceStatus


def attendance_summary(student, *, since_days: int | None = None) -> dict:
    """
    Attendance computed from the stored records.

    Returns an explicit ``available: False`` shape when the term has no records
    yet, so the UI can say so instead of rendering a placeholder percentage.
    """

    qs = AttendanceRecord.objects.filter(student=student)
    if since_days:
        qs = qs.filter(date__gte=timezone.localdate() - timedelta(days=since_days))

    records = list(qs.select_related("subject", "subject__program"))
    if not records:
        return {
            "available": False,
            "message": "No attendance data available yet.",
            "overall_percentage": None,
            "counts": {status.label: 0 for status in AttendanceStatus},
            "subjects": [],
            "recent": [],
            "monthly_trend": [],
        }

    attended = sum(1 for r in records if r.status in ATTENDED_STATUSES)
    total = len(records)
    overall = round(attended / total * 100, 1) if total else None

    by_subject: dict[int, list] = defaultdict(list)
    subjects: dict[int, object] = {}
    for record in records:
        by_subject[record.subject_id].append(record)
        subjects[record.subject_id] = record.subject

    subject_rows = []
    for subject_id, rows in by_subject.items():
        subject = subjects[subject_id]
        hits = sum(1 for r in rows if r.status in ATTENDED_STATUSES)
        percentage = round(hits / len(rows) * 100, 1)
        subject_rows.append(
            {
                "subject_id": subject.id,
                "subject_code": subject.code,
                "subject_name": subject.name,
                "subject_color": subject.color_token,
                "percentage": percentage,
                "present": sum(1 for r in rows if r.status == AttendanceStatus.PRESENT),
                "absent": sum(1 for r in rows if r.status == AttendanceStatus.ABSENT),
                "late": sum(1 for r in rows if r.status == AttendanceStatus.LATE),
                "excused": sum(1 for r in rows if r.status == AttendanceStatus.EXCUSED),
                "on_duty": sum(1 for r in rows if r.status == AttendanceStatus.ON_DUTY),
                "total_classes": len(rows),
            }
        )
    subject_rows.sort(key=lambda row: row["percentage"])

    counts = {status.label: 0 for status in AttendanceStatus}
    for record in records:
        counts[record.get_status_display()] += 1

    recent = [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "subject_id": r.subject_id,
            "subject_code": r.subject.code,
            "subject_name": r.subject.name,
            "subject_color": r.subject.color_token,
            "status": r.status,
            "status_label": r.get_status_display(),
            "period_label": r.period_label,
            "note": r.note,
        }
        for r in sorted(records, key=lambda r: r.date, reverse=True)[:30]
    ]

    monthly: dict[tuple[int, int], list] = defaultdict(list)
    for record in records:
        monthly[(record.date.year, record.date.month)].append(record)
    trend = []
    for (year, month), rows in sorted(monthly.items())[-6:]:
        hits = sum(1 for r in rows if r.status in ATTENDED_STATUSES)
        trend.append(
            {
                "label": f"{_month_name(month)[:3]} {year}",
                "percentage": round(hits / len(rows) * 100, 1),
                "total_classes": len(rows),
            }
        )

    return {
        "available": True,
        "overall_percentage": overall,
        "total_classes": total,
        "attended_classes": attended,
        "counts": counts,
        "subjects": subject_rows,
        "recent": recent,
        "monthly_trend": trend,
        "lowest_subject": subject_rows[0] if subject_rows else None,
    }


_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _month_name(month: int) -> str:
    return _MONTHS[month - 1]


def attendance_totals(qs) -> dict:
    total = qs.count()
    attended = qs.filter(status__in=list(ATTENDED_STATUSES)).count()
    return {
        "total": total,
        "attended": attended,
        "percentage": round(attended / total * 100, 1) if total else None,
    }


def latest_records(student, limit: int = 5):
    return list(
        AttendanceRecord.objects.filter(student=student)
        .select_related("subject")
        .order_by("-date", "subject__code")[:limit]
    )
