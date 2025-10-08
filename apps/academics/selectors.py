from .models import Group, GroupMembership


def get_workspace_groups(*, workspace, active_only=True):
    groups = Group.objects.filter(workspace=workspace).select_related("subject")

    if active_only:
        groups = groups.filter(is_active=True)

    return groups.order_by("name", "id")

def get_active_group_memberships(*, workspace, group_id):
    return (
        GroupMembership.objects
        .filter(
            group_id=group_id,
            group__workspace=workspace,
            student__workspace=workspace,
            left_at__isnull=True
        )
        .select_related("student")
        .order_by(
            "student__last_name",
            "student__first_name",
            "id"
        )
    )

def get_group_membership_history(*, workspace, group_id):
    return (
        GroupMembership.objects
        .filter(
            group_id=group_id,
            group__workspace=workspace,
            student__workspace=workspace
        )
        .select_related("student")
        .order_by(
            "-joined_at",
            "id"
        )
    )