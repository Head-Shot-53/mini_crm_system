from django.core.exceptions import ValidationError

from apps.workspaces.models import Workspace

from apps.lessons.selectors import get_schedule_conflicts


def lock_workspace_for_scheduling(*, workspace):
    return (
        Workspace.objects
        .select_for_update()
        .get(
            id=workspace.id
        )
    )


def ensure_slot_available(*, workspace, start_at, end_at, exclude_lesson_id=None):
    conflicts = get_schedule_conflicts(
        workspace=workspace,
        start_at=start_at,
        end_at=end_at,
        exclude_lesson_id=exclude_lesson_id
    )

    if conflicts.exists():
        raise ValidationError(
            "Another lesson already occupies "
            "this time interval."
        )