from django.core.exceptions import PermissionDenied

from .models import Workspace


def get_user_workspace(user):
    workspaces = list(Workspace.objects.filter(owner=user).order_by("id")[:2])

    if not workspaces:
        return None

    if len(workspaces) > 1:
        raise PermissionDenied(
            "Multiple workspaces are not supported in V1."
        )

    return workspaces[0]