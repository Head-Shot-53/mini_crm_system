from datetime import timedelta

import pytest
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.contrib.auth import get_user_model


from apps.homework.models import Assignment, AssignmentRecipient,AssignmentSubmission, AssignmentSubmissionAttempt
from apps.homework.services.publication import publish_assignment
from apps.homework.services.submissions import submit_assignment_work

from apps.academics.services import assign_subject_to_student

from apps.academics.models import Subject

from apps.students.models import Student

from apps.workspaces.models import Workspace


@pytest.fixture
def workspace(db):
    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(
        owner=teacher,
        name="Test Workspace"
    )


@pytest.fixture
def subject(db, workspace):
    return Subject.objects.create(
        workspace=workspace,
        name="Python"
    )


@pytest.fixture
def student(db, workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )


@pytest.fixture
def enrollment(db, workspace, subject, student):
    return assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        level="Beginner"
    )


@pytest.fixture
def deadline():
    return timezone.now() + timedelta(days=7)


pytestmark = pytest.mark.django_db


def test_first_submission_creates_submission_and_attempt(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    submission, attempt = (
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="My solution.",
            recorded_by=workspace.owner
        )
    )

    assert submission.recipient == recipient

    assert submission.status ==  AssignmentSubmission.Status.SUBMITTED

    assert submission.is_late is False

    assert submission.first_submitted_at == submission.last_submitted_at

    assert attempt.revision == 1

    assert attempt.answer_text == "My solution."

    assert attempt.is_late is False


def test_resubmission_creates_new_revision(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(assignment=assignment)

    submission, first_attempt = (
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Version 1",
            recorded_by=workspace.owner
        )
    )

    same_submission, second_attempt = (
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Version 2",
            recorded_by=workspace.owner
        )
    )

    assert same_submission.id == submission.id

    assert first_attempt.revision == 1

    assert second_attempt.revision == 2

    assert AssignmentSubmission.objects.filter(recipient=recipient).count() == 1

    assert AssignmentSubmissionAttempt.objects.filter(submission=submission).count() == 2


def test_resubmission_preserves_previous_content(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = assignment.recipients.get()

    submission, first_attempt = (
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Old answer",
            recorded_by=workspace.owner
        )
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="New answer",
        recorded_by=workspace.owner
    )

    first_attempt.refresh_from_db()

    assert first_attempt.answer_text == "Old answer"


def test_late_first_submission(workspace, subject, student):
    now = timezone.now()

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        status=Assignment.Status.PUBLISHED,
        published_at=now - timedelta(days=3),
        due_at=now - timedelta(days=1)
    )

    recipient = AssignmentRecipient.objects.create(
        assignment=assignment,
        student=student,
        assigned_at=assignment.published_at
    )

    submission, attempt = (
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Late solution.",
            recorded_by=workspace.owner
        )
    )

    assert submission.is_late is True

    assert submission.display_status == "late"

    assert attempt.is_late is True


def test_cannot_submit_draft_assignment(workspace, subject, student):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Draft Homework"
    )

    recipient = AssignmentRecipient.objects.create(
        assignment=assignment,
        student=student,
        assigned_at=timezone.now()
    )

    with pytest.raises(ValidationError):
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Answer",
            recorded_by=workspace.owner
        )

    assert not AssignmentSubmission.objects.filter(recipient=recipient).exists()


@pytest.mark.django_db
def test_closed_assignment_rejects_new_submission(workspace, subject, student,enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        description="Complete exercises.",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    assignment.status = Assignment.Status.CLOSED
    assignment.save(update_fields=["status"])

    attempts_before = AssignmentSubmissionAttempt.objects.filter(submission__recipient=recipient).count()

    submissions_before = AssignmentSubmission.objects.filter(recipient=recipient).count()

    with pytest.raises(ValidationError):
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="My solution",
            recorded_by=workspace.owner
        )

    attempts_after = AssignmentSubmissionAttempt.objects.filter(submission__recipient=recipient,).count()

    submissions_after = AssignmentSubmission.objects.filter(recipient=recipient).count()

    assert attempts_after == attempts_before
    assert submissions_after == submissions_before

    assert attempts_after == 0
    assert submissions_after == 0


@pytest.mark.django_db
def test_closed_assignment_rejects_resubmission(workspace, subject, student, enrollment,  deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        description="Complete exercises.",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    submission, first_attempt = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="First solution",
        recorded_by=workspace.owner
    )

    attempts_before = AssignmentSubmissionAttempt.objects.filter(
        submission=submission
    ).count()

    assert attempts_before == 1
    assert first_attempt.revision == 1

    assignment.status = Assignment.Status.CLOSED
    assignment.save(
        update_fields=["status"]
    )

    with pytest.raises(ValidationError):
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="Second solution",
            recorded_by=workspace.owner
        )

    submission.refresh_from_db()

    attempts_after = AssignmentSubmissionAttempt.objects.filter(submission=submission,).count()

    assert attempts_after == attempts_before
    assert attempts_after == 1

    assert AssignmentSubmission.objects.filter(recipient=recipient).count() == 1


def test_submission_requires_content(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = assignment.recipients.get()

    with pytest.raises(ValidationError):
        submit_assignment_work(
            workspace=workspace,
            recipient_id=recipient.id,
            answer_text="   ",
            answer_url="",
            recorded_by=workspace.owner
        )

    assert not AssignmentSubmission.objects.filter(recipient=recipient).exists()


@pytest.mark.django_db
def test_cannot_submit_work_for_foreign_recipient(workspace):
    User = get_user_model()


    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    foreign_student = Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    assign_subject_to_student(
        workspace=foreign_workspace,
        student_id=foreign_student.id,
        subject_id=foreign_subject.id,
        level="Beginner",
    )

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Assignment",
        description="Foreign homework.",
        due_at=timezone.now() + timedelta(days=7)
    )

    publish_assignment(
        workspace=foreign_workspace,
        assignment_id=foreign_assignment.id
    )

    foreign_recipient = AssignmentRecipient.objects.get(
        assignment=foreign_assignment,
        student=foreign_student
    )

    attempts_before = AssignmentSubmissionAttempt.objects.count()
    submissions_before = AssignmentSubmission.objects.count()


    with pytest.raises(AssignmentRecipient.DoesNotExist):
        submit_assignment_work(
            workspace=workspace,
            recipient_id=foreign_recipient.id,
            answer_text="Unauthorized submission.",
            recorded_by=workspace.owner
        )


    assert AssignmentSubmission.objects.count() == submissions_before

    assert AssignmentSubmissionAttempt.objects.count() == attempts_before

    assert not AssignmentSubmission.objects.filter(recipient=foreign_recipient).exists()


@pytest.mark.django_db
def test_database_prevents_duplicate_submission_revision(workspace, subject, student, enrollment,  deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        description="Complete exercises.",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    submission, first_attempt = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="First solution",
        recorded_by=workspace.owner
    )

    attempt = AssignmentSubmissionAttempt.objects.get(
        submission=submission,
        revision=1
    )

    assert attempt.revision == 1

    attempts_before = AssignmentSubmissionAttempt.objects.filter(submission=submission).count()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssignmentSubmissionAttempt.objects.create(
                submission=submission,
                revision=1,
                answer_text="Duplicate revision",
                submitted_at=timezone.now(),
                recorded_by=workspace.owner
            )

    assert AssignmentSubmissionAttempt.objects.filter(submission=submission).count() == attempts_before

    assert AssignmentSubmissionAttempt.objects.filter(
        submission=submission,
        revision=1
    ).count() == 1


@pytest.mark.django_db
def test_database_prevents_multiple_submissions_for_same_recipient(workspace, subject, student, enrollment,  deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        description="Complete exercises.",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    submission, first_attempt = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="First solution",
        recorded_by=workspace.owner,
    )

    assert AssignmentSubmission.objects.filter(
        recipient=recipient
    ).count() == 1

    submissions_before = AssignmentSubmission.objects.count()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssignmentSubmission.objects.create(
                recipient=recipient
            )

    assert AssignmentSubmission.objects.count() == submissions_before

    assert AssignmentSubmission.objects.filter(
        recipient=recipient
    ).count() == 1

    assert AssignmentSubmission.objects.get(recipient=recipient).id == submission.id


def test_submission_rolls_back_if_attempt_fails(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = assignment.recipients.get()

    with patch(
        "apps.homework.services.submissions."
        "AssignmentSubmissionAttempt.save",
        side_effect=RuntimeError(
            "Simulated attempt failure"
        )
    ):

        with pytest.raises(RuntimeError):

            submit_assignment_work(
                workspace=workspace,
                recipient_id=recipient.id,
                answer_text="Answer",
                recorded_by=workspace.owner
            )

    assert not AssignmentSubmission.objects.filter(
        recipient=recipient
    ).exists()

    assert not AssignmentSubmissionAttempt.objects.filter(
        submission__recipient=recipient
    ).exists()