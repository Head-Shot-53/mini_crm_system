from django.contrib import admin

from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "workspace", "email", "status", "start_date", "created_at")

    list_filter = ("status", "workspace")

    search_fields = ("first_name", "last_name", "email", "phone")

    readonly_fields = ("id", "status", "archived_at", "status_before_archive", "created_at", "updated_at")

    ordering = ("last_name", "first_name")

    def has_delete_permission(self, request, obj=None):
        return False