from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.lessons.selectors import get_workspace_lessons

from .availability import lock_workspace_for_scheduling
from .attendance import initialize_lesson_attendance


@transaction.atomic
def change_lesson_status(*, workspace, lesson_id, action, reason=""):
    allowed_actions = {"complete", "cancel"}

    if action not in allowed_actions:
        raise ValidationError(
            "Unsupported lesson status action."
        )

    lock_workspace_for_scheduling(workspace=workspace)

    lesson = (
        Lesson.objects
        .select_for_update()
        .get(
            id=lesson_id,
            workspace=workspace
        )
    )

    is_accessible = (
        get_workspace_lessons(
            workspace=workspace
        )
        .filter(id=lesson.id)
        .exists()
    )

    if not is_accessible:
        raise Lesson.DoesNotExist(
            "Lesson not found."
        )

    if lesson.status != Lesson.Status.SCHEDULED:
        raise ValidationError(
            "Only scheduled lessons "
            "can change their status."
        )

    now = timezone.now()

    if action == "complete":

        if now < lesson.end_at:
            raise ValidationError(
                "Cannot complete a lesson "
                "before its scheduled end."
            )

        lesson.status = Lesson.Status.COMPLETED

        lesson.completed_at = now

        lesson.cancelled_at = None

        lesson.cancellation_reason = ""

    elif action == "cancel":

        if now >= lesson.start_at:
            raise ValidationError(
                "A lesson that has already started "
                "cannot be cancelled."
            )

        lesson.status = Lesson.Status.CANCELLED

        lesson.cancelled_at = now

        lesson.completed_at = None

        lesson.cancellation_reason = reason.strip()

    lesson.full_clean()

    lesson.save(
        update_fields=[
            "status",
            "completed_at",
            "cancelled_at",
            "cancellation_reason",
            "updated_at"
        ]
    )

    if action == "complete":

        initialize_lesson_attendance(
            workspace=workspace,
            lesson=lesson,
            timestamp=now
        )

    return lesson


def cancel_future_individual_lessons_for_archived_student(*, workspace, student, timestamp):
    """
    Must be called inside the student archival transaction.

    The caller must acquire the Workspace lock
    before acquiring the Student lock.
    """

    return (
        Lesson.objects
        .filter(
            workspace=workspace,
            student=student,
            group__isnull=True,
            subject__workspace=workspace,
            status=Lesson.Status.SCHEDULED,
            start_at__gt=timestamp
        )
        .update(
            status=Lesson.Status.CANCELLED,
            cancelled_at=timestamp,
            completed_at=None,
            cancellation_reason="Student archived.",
            updated_at=timestamp
        )
    )