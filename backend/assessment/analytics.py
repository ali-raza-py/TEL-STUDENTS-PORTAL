"""
Academic analytics.

Everything here is computed from published TEL records. When the underlying
data is not rich enough for a given analysis the response says so explicitly
(``available: false`` with a reason) rather than returning a plausible looking
number.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

from assessment.models import Result, ResultItem, ResultStatus

TOPIC_ANALYSIS_UNAVAILABLE = (
    "Topic-level analysis will become available when question-level topic data "
    "is connected."
)


@dataclass
class SubjectPerformance:
    subject_id: int
    subject_code: str
    subject_name: str
    subject_color: str
    average_percentage: float
    assessments: int
    best_percentage: float
    latest_percentage: float | None
    latest_assessment: str | None
    latest_date: str | None
    trend: list[dict] = field(default_factory=list)
    weakest_item: str | None = None


@dataclass
class WeakSubject:
    subject_id: int
    subject_code: str
    subject_name: str
    subject_color: str
    recent_average: float
    overall_average: float
    assessments: int
    threshold: float
    severity: str
    reason: str
    recent_scores: list[dict]
    recommendation: str


def _result_scope(student) -> "object":
    return Result.objects.visible_to_students().filter(student=student)


def subject_performance(student, *, limit: int | None = None) -> list[SubjectPerformance]:
    qs = (
        _result_scope(student)
        .select_related("subject")
        .order_by("subject_id", "assessment_date", "created_at")
    )
    buckets: dict[int, list[Result]] = defaultdict(list)
    subjects: dict[int, object] = {}
    for result in qs:
        buckets[result.subject_id].append(result)
        subjects[result.subject_id] = result.subject

    performance: list[SubjectPerformance] = []
    for subject_id, results in buckets.items():
        subject = subjects[subject_id]
        percentages = [float(r.percentage) for r in results]
        recent = results[-5:]
        latest = results[-1]
        trend = [
            {
                "label": r.assessment_name,
                "date": r.assessment_date.isoformat(),
                "percentage": float(r.percentage),
            }
            for r in results[-8:]
        ]
        performance.append(
            SubjectPerformance(
                subject_id=subject.id,
                subject_code=subject.code,
                subject_name=subject.name,
                subject_color=subject.color_token,
                average_percentage=round(sum(percentages) / len(percentages), 1),
                assessments=len(results),
                best_percentage=round(max(percentages), 1),
                latest_percentage=float(latest.percentage),
                latest_assessment=latest.assessment_name,
                latest_date=latest.assessment_date.isoformat(),
                trend=trend,
                weakest_item=_weakest_item(student=student, subject_id=subject.id),
            )
        )

    performance.sort(key=lambda p: p.average_percentage, reverse=True)
    if limit:
        return performance[:limit]
    return performance


def _weakest_item(*, student, subject_id: int) -> str | None:
    """Lowest scoring chapter/topic for a subject, in a single aggregate query."""

    rows = (
        ResultItem.objects.filter(
            result__student=student,
            result__status=ResultStatus.PUBLISHED,
            result__subject_id=subject_id,
        )
        .values("chapter", "topic")
        .annotate(obtained=Sum("marks_awarded"), total=Sum("marks_total"))
    )
    worst: tuple[float, str] | None = None
    for row in rows:
        total = row["total"] or Decimal("0")
        if total <= 0:
            continue
        ratio = float(row["obtained"]) / float(total) * 100
        label = row["topic"] or row["chapter"]
        if not label:
            continue
        if worst is None or ratio < worst[0]:
            worst = (ratio, label)
    if worst is None:
        return None
    return f"{worst[1]} ({round(worst[0])}%)"


def overall_average(student) -> float | None:
    value = _result_scope(student).aggregate(avg=Avg("percentage"))["avg"]
    return round(float(value), 1) if value is not None else None


def detect_weak_subjects(
    student, *, threshold: float | None = None, min_assessments: int | None = None
) -> list[WeakSubject]:
    """
    Flags subjects whose recent published average falls below the TEL threshold.

    The reason string always states the numbers that triggered the flag so a
    student can see the reasoning rather than an unexplained verdict.
    """

    threshold = settings.TEL_WEAK_SUBJECT_SCORE if threshold is None else threshold
    min_assessments = (
        settings.TEL_WEAK_SUBJECT_MIN_ATTEMPTS if min_assessments is None else min_assessments
    )

    flagged: list[WeakSubject] = []
    for subject in subject_performance(student):
        if subject.assessments < min_assessments:
            continue
        recent = subject.trend[-3:]
        if not recent:
            continue
        recent_average = round(sum(item["percentage"] for item in recent) / len(recent), 1)
        if recent_average >= threshold:
            continue

        gap = round(threshold - recent_average, 1)
        if recent_average < threshold - 15:
            severity = "high"
        elif recent_average < threshold - 7:
            severity = "moderate"
        else:
            severity = "watch"

        reason = (
            f"Recent average of {recent_average}% across {len(recent)} "
            f"{'assessment' if len(recent) == 1 else 'assessments'} is {gap}% below the "
            f"{threshold:.0f}% TEL attention threshold."
        )
        if subject.weakest_item:
            reason += f" Lowest recorded area: {subject.weakest_item}."

        recommendation = {
            "high": "Book a revision session with your subject teacher and attempt the past paper archive.",
            "moderate": "Revisit the flagged chapters, then reattempt the most recent paper in practice mode.",
            "watch": "Keep the trend under observation and review the flagged area before the next test.",
        }[severity]

        flagged.append(
            WeakSubject(
                subject_id=subject.subject_id,
                subject_code=subject.subject_code,
                subject_name=subject.subject_name,
                subject_color=subject.subject_color,
                recent_average=recent_average,
                overall_average=subject.average_percentage,
                assessments=subject.assessments,
                threshold=threshold,
                severity=severity,
                reason=reason,
                recent_scores=recent,
                recommendation=recommendation,
            )
        )

    flagged.sort(key=lambda w: w.recent_average)
    return flagged


def topic_analysis(student, subject_id: int | None = None) -> dict:
    """
    Topic level breakdown — only when the result records actually carry topics.
    """

    base = ResultItem.objects.filter(
        result__student=student, result__status=ResultStatus.PUBLISHED
    ).exclude(topic="")
    if subject_id:
        base = base.filter(result__subject_id=subject_id)

    if not base.exists():
        return {
            "available": False,
            "reason": TOPIC_ANALYSIS_UNAVAILABLE,
            "topics": [],
        }

    rows = (
        base.values("result__subject_id", "result__subject__code", "result__subject__name",
                    "result__subject", "chapter", "topic")
        .annotate(obtained=Sum("marks_awarded"), total=Sum("marks_total"))
        .order_by("result__subject__code", "topic")
    )

    topics = []
    for row in rows:
        total = row["total"] or Decimal("0")
        if total <= 0:
            continue
        percentage = round(float(row["obtained"]) / float(total) * 100, 1)
        topics.append(
            {
                "subject_id": row["result__subject_id"],
                "subject_code": row["result__subject__code"],
                "subject_name": row["result__subject__name"],
                "chapter": row["chapter"],
                "topic": row["topic"],
                "obtained": float(row["obtained"]),
                "total": float(total),
                "percentage": percentage,
                "status": "strong" if percentage >= 80 else "steady" if percentage >= 60 else "needs_attention",
            }
        )

    if not topics:
        return {
            "available": False,
            "reason": TOPIC_ANALYSIS_UNAVAILABLE,
            "topics": [],
        }

    return {"available": True, "reason": "", "topics": topics}


def progress_summary(student) -> dict:
    """Overall academic position used by the dashboard progress card."""

    qs = _result_scope(student)
    totals = qs.aggregate(
        count=Count("id"),
        average=Avg("percentage"),
        best=Max("percentage"),
        worst=Min("percentage"),
    )
    if not totals["count"]:
        return {
            "available": False,
            "message": "No published results yet. Your progress will appear once TEL releases a result.",
            "assessments": 0,
        }

    by_type = list(
        qs.values("assessment_type")
        .annotate(average=Avg("percentage"), count=Count("id"))
        .order_by("assessment_type")
    )
    from assessment.models import ExamType

    return {
        "available": True,
        "assessments": totals["count"],
        "average_percentage": round(float(totals["average"]), 1),
        "best_percentage": round(float(totals["best"]), 1),
        "lowest_percentage": round(float(totals["worst"]), 1),
        "by_type": [
            {
                "assessment_type": row["assessment_type"],
                "label": ExamType(row["assessment_type"]).label,
                "average": round(float(row["average"]), 1),
                "count": row["count"],
            }
            for row in by_type
        ],
        "generated_at": timezone.now().isoformat(),
    }


def asdict_row(item):
    """Serialises a dataclass row (or passes a plain dict straight through)."""

    if hasattr(item, "__dataclass_fields__"):
        return asdict(item)
    return item


serialise = asdict_row
