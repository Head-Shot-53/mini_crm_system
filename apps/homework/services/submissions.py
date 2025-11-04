from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.homework.models import Assignment, AssignmentRecipient, AssignmentSubmission, AssignmentSubmissionAttempt


@transaction.atomic
def submit_assignment_work(*, workspace, recipient_id, answer_text="", answer_url="", recorded_by):
    answer_text = (answer_text or "").strip()

    answer_url = (answer_url or "").strip()

    if not answer_text and not answer_url:
        raise ValidationError(
            "Submission must contain text "
            "or a URL."
        )

    if len(answer_text) > 20_000:
        raise ValidationError(
            "Submission text cannot exceed "
            "20000 characters."
        )

    if answer_url:
        validator = URLValidator()

        try:
            validator(answer_url)

        except ValidationError:
            raise ValidationError(
                "Submission URL is invalid."
            )

    if recorded_by.pk != workspace.owner_id:
        raise ValidationError(
            "Only the workspace owner "
            "can record submissions in V1."
        )

    if not recorded_by.is_active:
        raise ValidationError(
            "Inactive users cannot "
            "record submissions."
        )

    scoped_recipient = (
        AssignmentRecipient.objects
        .select_related(
            "assignment",
            "student"
        )
        .get(
            id=recipient_id,
            assignment__workspace=workspace,
            student__workspace=workspace
        )
    )

    assignment = (
        Assignment.objects
        .select_for_update()
        .get(
            id=scoped_recipient.assignment_id,
            workspace=workspace
        )
    )

    recipient = (
        AssignmentRecipient.objects
        .select_for_update()
        .select_related("student")
        .get(
            id=scoped_recipient.id,
            assignment=assignment,
            student__workspace=workspace
        )
    )

    if assignment.status != Assignment.Status.PUBLISHED:
        raise ValidationError(
            "Submissions are only accepted "
            "for published assignments."
        )

    if assignment.due_at is None:
        raise ValidationError(
            "Published assignment has no deadline."
        )

    submitted_at = timezone.now()

    submission = (
        AssignmentSubmission.objects
        .select_for_update()
        .filter(recipient=recipient)
        .first()
    )

    if submission is None:

        first_is_late = submitted_at > assignment.due_at

        submission = AssignmentSubmission(
            recipient=recipient,
            status=(AssignmentSubmission.Status.SUBMITTED),
            is_late=first_is_late,
            first_submitted_at=submitted_at,
            last_submitted_at=submitted_at
        )

        submission.full_clean()
        submission.save()

    else:

        submission.last_submitted_at = (
            submitted_at
        )


        submission.status = (
            AssignmentSubmission.Status.SUBMITTED
        )

        submission.reviewed_at = None
        submission.reviewed_by = None
        submission.teacher_feedback = ""

        submission.full_clean()

        submission.save(
            update_fields=[
                "last_submitted_at",
                "status",
                "reviewed_at",
                "reviewed_by",
                "teacher_feedback",
                "updated_at"
            ]
        )

    max_revision = (
        AssignmentSubmissionAttempt.objects
        .filter(submission=submission)
        .aggregate(value=Max("revision"))["value"] or 0
    )

    revision = max_revision + 1

    attempt = AssignmentSubmissionAttempt(
        submission=submission,
        revision=revision,
        answer_text=answer_text,
        answer_url=answer_url,
        submitted_at=submitted_at,
        is_late=(submitted_at > assignment.due_at),
        recorded_by=recorded_by
    )

    attempt.full_clean()
    attempt.save()

    return submission, attempt