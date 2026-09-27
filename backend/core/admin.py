from django.contrib import admin

from core.models import AuditLog, Notification, UploadRecord


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "category", "state", "created_at")
    list_filter = ("category", "state", "is_archived")
    search_fields = ("title", "body", "recipient__email")


@admin.register(UploadRecord)
class UploadRecordAdmin(admin.ModelAdmin):
    list_display = ("original_name", "purpose", "visibility", "uploader", "size", "created_at")
    list_filter = ("purpose", "visibility")
    search_fields = ("original_name", "checksum")
    readonly_fields = ("checksum", "size", "content_type", "storage_path")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "entity_type", "entity_id", "summary")
    list_filter = ("action", "entity_type", "actor_role")
    search_fields = ("action", "summary", "entity_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
