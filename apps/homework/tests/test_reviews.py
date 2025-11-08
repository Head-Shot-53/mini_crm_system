import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta


from apps.homework.models import Assignment, AssignmentRecipient, AssignmentSubmission
from apps.homework.services.reviews import review_submission

from apps.academics.models import Subject
from apps.students.models import Student
from apps.workspaces.models import Workspace

from apps.homework.services.publication import publish_assignment
from apps.homework.services.submissions import submit_assignment_work

from apps.academics.services import assign_subject_to_student


from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db

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
def foreign_workspace(db):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign-teacher@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

def create_submitted_work(*,  workspace, subject, student):
    assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        level="Beginner"
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Homework",
        description="Complete the homework.",
        due_at=timezone.now() + timedelta(days=7)
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    submission, attempt = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Student answer",
        recorded_by=workspace.owner
    )

    return submission

def test_review_submission(workspace, subject, student):
    submission = create_submitted_work(
        workspace=workspace,
        subject=subject,
        student=student
    )

    result = review_submission(
        workspace=workspace,
        submission_id=submission.id,
        reviewed_by=workspace.owner,
        teacher_feedback="Good work."
    )

    submission.refresh_from_db()

    assert result == submission

    assert submission.status == AssignmentSubmission.Status.REVIEWED

    assert submission.teacher_feedback == "Good work."
    

    assert  submission.reviewed_by == workspace.owner

    assert submission.reviewed_at is not None


def test_review_submission_strips_feedback(workspace, subject, student):
    submission = create_submitted_work(
        workspace=workspace,
        subject=subject,
        student=student
    )

    review_submission(
        workspace=workspace,
        submission_id=submission.id,
        reviewed_by=workspace.owner,
        teacher_feedback="   Nice solution.   "
    )

    submission.refresh_from_db()

    assert  submission.teacher_feedback == "Nice solution."



def test_reviewed_submission_cannot_be_reviewed_again(workspace, subject, student):
    submission = create_submitted_work(
        workspace=workspace,
        subject=subject,
        student=student
    )

    review_submission(
        workspace=workspace,
        submission_id=submission.id,
        reviewed_by=workspace.owner,
        teacher_feedback="First review."
    )

    with pytest.raises(ValidationError,  match="Only submitted work can be reviewed."):
        review_submission(
            workspace=workspace,
            submission_id=submission.id,
            reviewed_by=workspace.owner,
            teacher_feedback="Second review."
        )

    submission.refresh_from_db()

    assert submission.teacher_feedback == "First review."



def test_cannot_review_foreign_submission(workspace, subject, student, foreign_workspace):
    submission = create_submitted_work(
        workspace=workspace,
        subject=subject,
        student=student
    )

    with pytest.raises(AssignmentSubmission.DoesNotExist):
        review_submission(
            workspace=foreign_workspace,
            submission_id=submission.id,
            reviewed_by=foreign_workspace.owner,
            teacher_feedback="Invalid review."
        )

    submission.refresh_from_db()

    assert submission.status  == AssignmentSubmission.Status.SUBMITTED

    assert submission.reviewed_at is None