from django.contrib import admin

from academics.models import (
    AcademicYear,
    Campus,
    ClassRepresentative,
    ClassRoom,
    Program,
    Section,
    Subject,
    SubjectOffering,
    Timetable,
    TimetableEntry,
    TimetableSubmission,
)


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phone", "is_active")
    search_fields = ("code", "name")


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "department", "is_active")
    search_fields = ("code", "name")


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "start_date", "end_date", "is_current", "is_locked")
    list_filter = ("is_current", "is_locked")
    search_fields = ("code", "label")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "class_room", "capacity", "room", "is_active")
    list_filter = ("class_room", "is_active")
    search_fields = ("name", "class_room__code", "class_room__name")


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "program", "campus", "academic_year", "is_active")
    list_filter = ("campus", "program", "academic_year", "is_active")
    search_fields = ("code", "name")
    inlines = [SectionInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "program", "kind", "credit_hours", "is_active")
    list_filter = ("program", "kind", "is_active", "is_elective")
    search_fields = ("code", "name")


@admin.register(SubjectOffering)
class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = ("subject", "class_room", "section", "teacher", "academic_year", "is_active")
    list_filter = ("class_room", "academic_year", "is_active")
    autocomplete_fields = ("subject", "class_room", "section", "teacher")


class TimetableEntryInline(admin.TabularInline):
    model = TimetableEntry
    extra = 0


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ("class_room", "section", "version", "status", "effective_from", "published_at")
    list_filter = ("status", "class_room", "source")
    inlines = [TimetableEntryInline]


@admin.register(TimetableSubmission)
class TimetableSubmissionAdmin(admin.ModelAdmin):
    list_display = ("pk", "class_room", "section", "submitted_by", "status", "created_at")
    list_filter = ("status", "class_room")
    readonly_fields = ("public_id", "reviewed_at")


@admin.register(ClassRepresentative)
class ClassRepresentativeAdmin(admin.ModelAdmin):
    list_display = ("user", "class_room", "section", "is_active", "starts_on", "ends_on")
    list_filter = ("is_active", "class_room")
    autocomplete_fields = ("user", "class_room", "section", "assigned_by")
