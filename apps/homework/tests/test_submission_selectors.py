from datetime import timedelta

import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.academics.models import StudentSubject, Subject

from apps.homework.models import Assignment, AssignmentRecipient, AssignmentSubmission

from apps.homework.selectors import get_assignment_submission_overview, get_assignment_submissions, get_submission_attempts

from apps.homework.services.publication import publish_assignment

from apps.homework.services.submissions import submit_assignment_work

from apps.students.models import Student
from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
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
def subject(workspace):
    return Subject.objects.create(
        workspace=workspace,
        name="Python"
    )


@pytest.fixture
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )


@pytest.fixture
def enrollment(student, subject):
    return StudentSubject.objects.create(
        student=student,
        subject=subject
    )


@pytest.fixture
def deadline():
    return timezone.now() + timedelta(days=7)


@pytest.fixture
def published_assignment( workspace,subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        description="Complete exercises 1–10.",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    assignment.refresh_from_db()

    return assignment


@pytest.fixture
def recipient(published_assignment, student):
    return AssignmentRecipient.objects.get(
        assignment=published_assignment,
        student=student
    )


@pytest.fixture
def submission(workspace, recipient):
    submission, _ = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="My solution.",
        recorded_by=workspace.owner
    )

    return submission


def test_get_assignment_submissions_returns_submission(workspace, published_assignment, submission):
    submissions = list(
        get_assignment_submissions(
            workspace=workspace,
            assignment=published_assignment
        )
    )

    assert submissions == [submission]


def test_get_assignment_submissions_contains_recipient_and_student(workspace,  published_assignment, submission):
    submissions = list(
        get_assignment_submissions(
            workspace=workspace,
            assignment=published_assignment
        )
    )

    assert len(submissions) == 1

    result = submissions[0]

    assert result.id == submission.id

    assert result.recipient.id == submission.recipient.id

    assert (
        result.recipient.student.id == submission.recipient.student.id
    )

    assert (
        result.recipient.assignment.id == published_assignment.id
    )


def test_get_assignment_submissions_does_not_return_foreign_workspace_data(workspace, published_assignment, submission):
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

    StudentSubject.objects.create(
        student=foreign_student,
        subject=foreign_subject
    )

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="English Homework",
        due_at=timezone.now() + timedelta(days=5)
    )

    publish_assignment(
        workspace=foreign_workspace,
        assignment_id=foreign_assignment.id
    )

    foreign_recipient = AssignmentRecipient.objects.get(
        assignment=foreign_assignment,
        student=foreign_student
    )

    foreign_submission, _ = submit_assignment_work(
        workspace=foreign_workspace,
        recipient_id=foreign_recipient.id,
        answer_text="Foreign answer.",
        recorded_by=foreign_workspace.owner
    )

    own_submissions = list(
        get_assignment_submissions(
            workspace=workspace,
            assignment=published_assignment
        )
    )

    assert own_submissions == [submission]

    assert foreign_submission not in own_submissions



def test_get_submission_attempts_returns_all_revisions(workspace, recipient,):
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

    attempts = list(
        get_submission_attempts(
            workspace=workspace,
            submission=submission
        )
    )

    assert len(attempts) == 2

    attempt_ids = {
        attempt.id
        for attempt in attempts
    }

    assert attempt_ids == {
        first_attempt.id,
        second_attempt.id
    }


def test_get_submission_attempts_are_ordered_by_revision_desc(workspace, recipient):
    submission, _ = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Version 1",
        recorded_by=workspace.owner
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Version 2",
        recorded_by=workspace.owner
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Version 3",
        recorded_by=workspace.owner
    )

    attempts = list(
        get_submission_attempts(
            workspace=workspace,
            submission=submission
        )
    )

    revisions = [
        attempt.revision
        for attempt in attempts
    ]

    assert revisions == [3,2,1]


def test_get_submission_attempts_preserves_revision_content(workspace, recipient):
    submission, _ = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Old solution",
        recorded_by=workspace.owner
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Updated solution",
        recorded_by=workspace.owner
    )

    attempts = list(
        get_submission_attempts(
            workspace=workspace,
            submission=submission
        )
    )

    assert attempts[0].revision == 2
    assert attempts[0].answer_text == "Updated solution"

    assert attempts[1].revision == 1
    assert attempts[1].answer_text == "Old solution"


def test_assignment_submission_overview_returns_recipient_with_submission(workspace, published_assignment, recipient, submission):
    overview = list(
        get_assignment_submission_overview(
            workspace=workspace,
            assignment=published_assignment,
        )
    )

    assert len(overview) == 1

    overview_recipient = overview[0]

    assert overview_recipient.id == recipient.id

    assert (
        overview_recipient.submission.id
        == submission.id
    )


def test_assignment_submission_overview_contains_recipient_without_submission(workspace, subject, deadline):
    first_student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    second_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov"
    )

    StudentSubject.objects.create(
        student=first_student,
        subject=subject
    )

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=first_student,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=first_student
    )

    overview = list(
        get_assignment_submission_overview(
            workspace=workspace,
            assignment=assignment
        )
    )

    assert len(overview) == 1

    assert overview[0] == recipient

    assert not AssignmentSubmission.objects.filter(
        recipient=recipient
    ).exists()


def test_submission_overview_does_not_return_foreign_recipients(workspace, published_assignment, recipient):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign-overview@example.com",
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

    StudentSubject.objects.create(
        student=foreign_student,
        subject=foreign_subject
    )

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Homework",
        due_at=timezone.now() + timedelta(days=7)
    )

    publish_assignment(
        workspace=foreign_workspace,
        assignment_id=foreign_assignment.id
    )

    foreign_recipient = AssignmentRecipient.objects.get(
        assignment=foreign_assignment
    )

    overview = list(
        get_assignment_submission_overview(
            workspace=workspace,
            assignment=published_assignment
        )
    )

    assert recipient in overview

    assert foreign_recipient not in overview



def test_assignment_submissions_selector_avoids_n_plus_one(django_assert_num_queries, workspace, published_assignment, submission):
    with django_assert_num_queries(1):

        submissions = list(
            get_assignment_submissions(
                workspace=workspace,
                assignment=published_assignment
            )
        )

        for item in submissions:
            _ = item.recipient.student.first_name
            _ = item.recipient.student.last_name
            _ = item.recipient.assignment.title
            _ = item.reviewed_by

    assert len(submissions) == 1


def test_submission_attempts_selector_avoids_n_plus_one(django_assert_num_queries, workspace, recipient):
    submission, _ = submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Version 1",
        recorded_by=workspace.owner
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Version 2",
        recorded_by=workspace.owner
    )

    with django_assert_num_queries(1):

        attempts = list(
            get_submission_attempts(
                workspace=workspace,
                submission=submission
            )
        )

        for attempt in attempts:
            _ = attempt.recorded_by

    assert len(attempts) == 2