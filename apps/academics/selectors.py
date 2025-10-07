from .models import Group


def get_workspace_groups(*, workspace, active_only=True):
    groups = Group.objects.filter(workspace=workspace).select_related("subject")

    if active_only:
        groups = groups.filter(is_active=True)

    return groups.order_by("name", "id")