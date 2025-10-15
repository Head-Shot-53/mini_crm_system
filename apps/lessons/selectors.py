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