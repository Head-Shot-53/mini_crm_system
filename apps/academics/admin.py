from django.contrib import admin

from .models import Subject, Group

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "workspace__name", "workspace__owner__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "workspace", "max_students", "is_active", "created_at")
    list_filter = ("is_active", "workspace", "subject")
    search_fields = ("name", "subject__name", "workspace__name")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("name",)