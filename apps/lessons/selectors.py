from django.db.models import F, Q

from .models import Lesson


def get_workspace_lessons(*, workspace):
    lessons = Lesson.objects.filter(
        workspace=workspace,
        subject__workspace=workspace
    )

    valid_individual = Q(
        student__isnull=False,
        student__workspace=workspace,
        group__isnull=True
    )

    valid_group = Q(
        group__isnull=False,
        group__workspace=workspace,
        group__subject_id=F("subject_id"),
        student__isnull=True
    )

    return (
        lessons
        .filter(valid_individual | valid_group)
        .select_related(
            "student",
            "group",
            "subject"
        )
        .order_by("start_at", "id"))


def get_schedule_conflicts(*, workspace, start_at, end_at, exclude_lesson_id=None):
    conflicts = Lesson.objects.filter(
        workspace=workspace,

        status__in=[
            Lesson.Status.SCHEDULED,
            Lesson.Status.COMPLETED
        ],

        start_at__lt=end_at,
        end_at__gt=start_at
    )

    if exclude_lesson_id is not None:
        conflicts = conflicts.exclude(
            id=exclude_lesson_id
        )

    return conflicts.order_by("start_at", "id")


def get_calendar_lessons(*, workspace, period_start, period_end):
    return (
        get_workspace_lessons(
            workspace=workspace,
        )
        .filter(
            start_at__lt=period_end,
            end_at__gt=period_start
        )
    )