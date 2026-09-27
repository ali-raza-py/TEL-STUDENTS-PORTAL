from django.contrib import admin

from assessment.models import (
    Paper,
    PaperQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Result,
    ResultItem,
    ResultPublication,
)


class PaperQuestionInline(admin.TabularInline):
    model = PaperQuestion
    extra = 0


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "exam_type", "class_room", "status", "exam_date")
    list_filter = ("status", "exam_type", "campus", "class_room", "source")
    search_fields = ("title", "external_ref")
    inlines = [PaperQuestionInline]


class ResultItemInline(admin.TabularInline):
    model = ResultItem
    extra = 0


class ResultPublicationInline(admin.TabularInline):
    model = ResultPublication
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("assessment_name", "student", "subject", "obtained_marks", "total_marks", "status")
    list_filter = ("status", "assessment_type", "subject")
    search_fields = ("assessment_name", "student__student_code", "student__user__full_name")
    inlines = [ResultItemInline, ResultPublicationInline]


@admin.register(PracticeAttempt)
class PracticeAttemptAdmin(admin.ModelAdmin):
    list_display = ("paper", "student", "attempt_number", "status", "score", "total_marks", "percentage")
    list_filter = ("status",)
    readonly_fields = ("public_id",)


@admin.register(PracticeAnswer)
class PracticeAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "selected_option", "is_correct", "marks_awarded")
    list_filter = ("is_auto_graded", "is_correct")
