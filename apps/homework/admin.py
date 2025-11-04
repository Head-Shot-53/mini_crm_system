from django.contrib import admin

from apps.workspaces.admin_security import ReadOnlyBusinessAdminMixin

from .models import Assignment, AssignmentRecipient, AssignmentSubmission, AssignmentSubmissionAttempt


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


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(ReadOnlyBusinessAdminMixin, admin.ModelAdmin):
    list_display = ("recipient", "status", "is_late", "first_submitted_at", "last_submitted_at", "reviewed_at")

    list_filter = ("status", "is_late")

    search_fields = (
        "recipient__student__first_name",
        "recipient__student__last_name",
        "recipient__assignment__title"
    )

    list_select_related = (
        "recipient",
        "recipient__student",
        "recipient__assignment",
        "reviewed_by"
    )


@admin.register(AssignmentSubmissionAttempt)
class AssignmentSubmissionAttemptAdmin(ReadOnlyBusinessAdminMixin,admin.ModelAdmin):
    list_display = ("submission", "revision", "submitted_at", "is_late", "recorded_by")

    list_filter = ("is_late",)

    search_fields = (
        "submission__recipient__student__first_name",
        "submission__recipient__student__last_name",
        "submission__recipient__assignment__title"
    )

    list_select_related = ("submission", "submission__recipient", "recorded_by")