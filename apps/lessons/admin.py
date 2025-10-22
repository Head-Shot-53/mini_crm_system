from django.contrib import admin

from apps.workspaces.admin_security import (
    ReadOnlyBusinessAdminMixin,
)

from .models import Lesson, LessonAttendance


@admin.register(Lesson)
class LessonAdmin(ReadOnlyBusinessAdminMixin, admin.ModelAdmin):

    list_display = ("subject", "lesson_type", "start_at", "end_at", "status", "workspace")

    list_filter = ("status", "subject", "workspace")

    search_fields = ( "subject__name", "student__first_name", "student__last_name", "group__name")

    list_select_related = ( "subject", "student", "group", "workspace")

    readonly_fields = (
        "id",
        "workspace",
        "subject",
        "student",
        "group",
        "start_at",
        "end_at",
        "status",
        "notes",
        "created_at",
        "updated_at",
    )

    ordering = ("-start_at",)

@admin.register(LessonAttendance)
class LessonAttendanceAdmin(ReadOnlyBusinessAdminMixin, admin.ModelAdmin):

    list_display = (
        "student",
        "lesson",
        "status",
        "recorded_at",
        "recorded_by"
    )

    list_filter = ("status", "lesson__status")

    search_fields = ("student__first_name", "student__last_name", "lesson__subject__name",)

    list_select_related = ("student", "lesson", "recorded_by")

    readonly_fields = (
        "id",
        "lesson",
        "student",
        "group_membership",
        "status",
        "notes",
        "recorded_at",
        "recorded_by",
        "created_at",
        "updated_at"
    )