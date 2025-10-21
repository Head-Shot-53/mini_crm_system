from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.lessons.models import Lesson

from .availability import ensure_slot_available, lock_workspace_for_scheduling

from .validators import validate_lesson_time


@transaction.atomic
def reschedule_lesson(*, workspace, lesson_id, start_at, end_at):
    validate_lesson_time(
        start_at=start_at,
        end_at=end_at
    )

    lock_workspace_for_scheduling(
        workspace=workspace
    )

    lesson = (
        Lesson.objects
        .select_for_update()
        .get(
            id=lesson_id,
            workspace=workspace
        )
    )

    if lesson.status != Lesson.Status.SCHEDULED:
        raise ValidationError(
            "Only scheduled lessons can be rescheduled."
        )

    if lesson.start_at <= timezone.now():
        raise ValidationError(
            "A lesson that has already started "
            "cannot be rescheduled."
        )

    ensure_slot_available(
        workspace=workspace,
        start_at=start_at,
        end_at=end_at,
        exclude_lesson_id=lesson.id
    )

    lesson.start_at = start_at
    lesson.end_at = end_at

    lesson.full_clean()

    lesson.save(
        update_fields=[
            "start_at",
            "end_at",
            "updated_at"
        ]
    )

    return lesson