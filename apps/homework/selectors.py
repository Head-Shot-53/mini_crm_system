from django.db.models import F, Q

from .models import Assignment, AssignmentRecipient


def get_workspace_assignments(*, workspace):
    valid_individual = Q(
        student__isnull=False,
        student__workspace=workspace,
        group__isnull=True
    )

    valid_group = Q(
        student__isnull=True,
        group__workspace=workspace,
        group__subject_id=F("subject_id")
    )

    valid_without_lesson = Q(lesson__isnull=True)

    valid_individual_lesson = Q(
        lesson__workspace=workspace,
        lesson__subject_id=F("subject_id"),
        lesson__student_id=F("student_id"),
        lesson__group__isnull=True,
        student__isnull=False
    )

    valid_group_lesson = Q(
        lesson__workspace=workspace,
        lesson__subject_id=F("subject_id"),
        lesson__group_id=F("group_id"),
        lesson__student__isnull=True,
        group__isnull=False
    )

    return (
        Assignment.objects
        .filter(
            workspace=workspace,
            subject__workspace=workspace
        )
        .filter(valid_individual | valid_group)
        .filter(
            valid_without_lesson
            | valid_individual_lesson
            | valid_group_lesson
        )
        .select_related("subject", "student", "group", "lesson")
        .order_by("-created_at", "id",
        )
    )


def get_assignment_recipients(*, workspace, assignment):
    recipients = (
        AssignmentRecipient.objects
        .filter(
            assignment=assignment,
            assignment__workspace=workspace,
            student__workspace=workspace
        )
    )

    valid_individual = Q(
        assignment__student_id=F("student_id"),
        assignment__group__isnull=True,
        group_membership__isnull=True
    )

    valid_group = Q(
        assignment__student__isnull=True,
        assignment__group__workspace=workspace,
        group_membership__group_id=F("assignment__group_id"),
        group_membership__student_id=F("student_id")
    )

    return (
        recipients
        .filter(
            valid_individual | valid_group
        )
        .select_related(
            "student",
            "assignment",
            "group_membership"
        )
        .order_by(
            "student__last_name",
            "student__first_name",
            "id"
        )
    )