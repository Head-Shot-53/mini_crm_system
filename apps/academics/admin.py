from django.contrib import admin

from .models import Subject

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "workspace__name", "workspace__owner__email")
    readonly_fields = ("id", "created_at", "updated_at")