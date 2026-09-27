from __future__ import annotations

from django.core.cache import cache
from django.db import models


class TimeStampedModel(models.Model):
    """Adds creation / modification bookkeeping to a model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPublicIdModel(models.Model):
    """
    Exposes a non-guessable public identifier for models students interact with.

    Requests (tickets, submissions, papers) are addressed by this value rather
    than the sequential primary key so that identifiers cannot be enumerated.
    """

    public_id = models.UUIDField(default=None, editable=False, unique=True, null=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.public_id is None:
            import uuid

            self.public_id = uuid.uuid4()
        return super().save(*args, **kwargs)


def cache_key(prefix: str, *parts: object) -> str:
    return ":".join([prefix, *[str(part) for part in parts]])


def invalidate_cache(prefix: str) -> None:
    """Best-effort prefix invalidation for the locmem/redis cache backends."""

    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern(f"{prefix}*")


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self) -> "SoftDeleteQuerySet":
        return self.filter(is_active=True)


class SoftDeleteModel(TimeStampedModel):
    is_active = models.BooleanField(default=True, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True
