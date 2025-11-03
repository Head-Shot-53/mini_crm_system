from django.contrib import admin

from apps.workspaces.admin_security import ReadOnlyBusinessAdminMixin

from .models import Assignment, AssignmentRecipient


@admin.register(Assignment)
class AssignmentAdmin(ReadOnlyBusinessAdminMixin, admin.ModelAdmin):

    list_display = ("title", "subject", "assignment_type", "status", "due_at", "published_at", "workspace")
    list_filter = ("status", "subject")
    search_fields = ("title", "student__first_name", "student__last_name", "group__name")
    list_select_related = ("workspace", "subject", "student", "group", "lesson")


@admin.register(AssignmentRecipient)
class AssignmentRecipientAdmin(ReadOnlyBusinessAdminMixin, admin.ModelAdmin):

    list_display = ("assignment", "student", "source", "assigned_at")
    list_filter = ("source",)
    search_fields = ("assignment__title", "student__first_name",  "student__last_name")
    list_select_related = ("assignment", "student", "group_membership")