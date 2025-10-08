from django.contrib import admin

from .models import Subject, Group, GroupMembership

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

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("student", "group", "joined_at", "left_at")
    list_filter = ( "group",)
    search_fields = ("student__first_name", "student__last_name", "group__name")
    readonly_fields = ("id", "student", "group", "joined_at", "left_at", "created_at")


    def has_add_permission(self, request):
        return False


    def has_change_permission(self, request, obj=None):
        return False


    def has_delete_permission(self, request, obj=None):
        return False