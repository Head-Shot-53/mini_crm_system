from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.homework.models import AssignmentSubmission


@transaction.atomic
def review_submission(*, workspace, submission_id, reviewed_by, teacher_feedback=""):
    submission = (
        AssignmentSubmission.objects
        .select_for_update()
        .select_related(
            "recipient",
            "recipient__assignment",
            "recipient__student"
        )
        .get(
            id=submission_id,
            recipient__assignment__workspace=workspace
        )
    )

    if reviewed_by != workspace.owner:
        raise ValidationError(
            "Only the workspace owner can review submissions."
        )

    if submission.status != AssignmentSubmission.Status.SUBMITTED:
        raise ValidationError(
            "Only submitted work can be reviewed."
        )

    submission.status = (AssignmentSubmission.Status.REVIEWED)

    submission.teacher_feedback = (teacher_feedback.strip())

    submission.reviewed_by = reviewed_by
    submission.reviewed_at = timezone.now()

    submission.full_clean()

    submission.save(
        update_fields=[
            "status",
            "teacher_feedback",
            "reviewed_by",
            "reviewed_at",
            "updated_at"
        ]
    )

    return submission