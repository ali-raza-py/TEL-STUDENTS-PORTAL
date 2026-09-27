from django.contrib import admin

from engagement.models import (
    AcademicEvent,
    Announcement,
    Assignment,
    AssignmentSubmission,
    AttendanceRecord,
    Feedback,
    Resource,
    StudentRequest,
)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "date", "status", "source")
    list_filter = ("status", "subject", "date")
    search_fields = ("student__student_code", "student__user__full_name")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "class_room", "assigned_on", "due_on", "is_published")
    list_filter = ("is_published", "subject", "class_room")
    search_fields = ("title",)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "status", "submitted_at", "marks_awarded")
    list_filter = ("status",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "subject", "is_published", "published_at")
    list_filter = ("category", "is_published")
    search_fields = ("title", "chapter")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "is_pinned", "is_published", "published_at")
    list_filter = ("audience", "is_pinned", "is_published")
    search_fields = ("title", "body")


@admin.register(AcademicEvent)
class AcademicEventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "starts_at", "is_all_day")
    list_filter = ("event_type", "is_all_day")
    search_fields = ("title",)


@admin.register(StudentRequest)
class StudentRequestAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "student", "request_type", "status", "created_at")
    list_filter = ("status", "request_type")
    search_fields = ("ticket_id", "subject_line", "student__user__full_name")
    readonly_fields = ("ticket_id", "public_id")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("category", "rating", "status", "created_at")
    list_filter = ("category", "status")
    search_fields = ("message",)
