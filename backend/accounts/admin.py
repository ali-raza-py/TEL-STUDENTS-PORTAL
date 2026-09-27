from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import StudentProfile, TeacherProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "full_name", "role", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name")
    ordering = ("full_name",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identity", {"fields": ("full_name", "phone", "role", "tel_user_ref")}),
        ("Placement", {"fields": ("campus", "class_room", "section", "academic_year")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "password_changed_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "is_active", "password1", "password2"),
            },
        ),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_code", "user", "campus", "class_room", "section", "status")
    list_filter = ("campus", "program", "class_room", "status")
    search_fields = ("student_code", "user__full_name", "user__email")
    autocomplete_fields = ("user", "campus", "program", "class_room", "section", "academic_year")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "designation", "campus")
    search_fields = ("employee_code", "user__full_name")
    filter_horizontal = ("subjects",)
