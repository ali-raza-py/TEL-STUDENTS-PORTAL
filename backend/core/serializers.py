from __future__ import annotations

from rest_framework import serializers

from core.models import AuditLog, Notification, NotificationState, UploadRecord


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "category",
            "state",
            "is_read",
            "title",
            "body",
            "action_url",
            "action_label",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields

    def get_is_read(self, obj: Notification) -> bool:
        return obj.state != NotificationState.UNREAD


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )
    all = serializers.BooleanField(required=False, default=False)


class UploadRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadRecord
        fields = [
            "id",
            "purpose",
            "original_name",
            "content_type",
            "size",
            "checksum",
            "visibility",
            "created_at",
        ]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_role",
            "action",
            "entity_type",
            "entity_id",
            "summary",
            "metadata",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields
