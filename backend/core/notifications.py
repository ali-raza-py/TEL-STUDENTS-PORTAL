"""
Notification delivery.

Every notification is written by a workflow event, deduplicated per student so
that repeated syncs cannot spam, and optionally mirrored to a WhatsApp-style
message queue (see ``telportal.integrations``) rather than replacing WhatsApp.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

from accounts.models import User
from academics.models import ClassRoom, Section
from core.models import Notification, NotificationCategory

logger = logging.getLogger("telportal.notifications")


def notify(
    recipient: User,
    *,
    category: str,
    title: str,
    body: str = "",
    action_url: str = "",
    action_label: str = "",
    dedupe_key: str = "",
) -> Notification | None:
    if recipient is None:
        return None
    if dedupe_key:
        existing = Notification.objects.filter(recipient=recipient, dedupe_key=dedupe_key).first()
        if existing:
            return existing
    try:
        return Notification.objects.create(
            recipient=recipient,
            category=category,
            title=title[:180],
            body=body,
            action_url=action_url[:300],
            action_label=action_label[:60],
            dedupe_key=dedupe_key[:200],
        )
    except IntegrityError:
        return Notification.objects.filter(recipient=recipient, dedupe_key=dedupe_key).first()


def notify_class(
    *,
    class_room: ClassRoom,
    section: Section | None,
    category: str,
    title: str,
    body: str = "",
    action_url: str = "",
    action_label: str = "",
    dedupe_suffix: str = "",
    exclude_user_ids: tuple[int, ...] = (),
) -> int:
    """Fans a notification out to every active placement in a class section."""

    from accounts.models import StudentProfile

    placements = StudentProfile.objects.filter(
        class_room=class_room,
        academic_year__isnull=False,
    ).select_related("user")
    if section is not None:
        placements = placements.filter(section=section)

    created = 0
    for placement in placements:
        if placement.user_id in exclude_user_ids:
            continue
        result = notify(
            placement.user,
            category=category,
            title=title,
            body=body,
            action_url=action_url,
            action_label=action_label,
            dedupe_key=f"{category}:{class_room.pk}:{section.pk if section else 0}:{dedupe_suffix}",
        )
        if result is not None:
            created += 1
    return created


def prune_old_notifications(days: int = 180) -> int:
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return deleted


def students_for_audience(
    *,
    campus_id: int | None = None,
    program_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    academic_year_id: int | None = None,
) -> list[User]:
    from accounts.models import StudentProfile

    qs = StudentProfile.objects.filter(status=StudentProfile.Status.ACTIVE).select_related("user")
    if campus_id:
        qs = qs.filter(campus_id=campus_id)
    if program_id:
        qs = qs.filter(program_id=program_id)
    if class_id:
        qs = qs.filter(class_room_id=class_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if academic_year_id:
        qs = qs.filter(academic_year_id=academic_year_id)
    return [p.user for p in qs if p.user.is_active]


CATEGORY = NotificationCategory
