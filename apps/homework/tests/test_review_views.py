import pytest

from datetime import timedelta
from django.utils import timezone
from django.test import Client

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.homework.models import AssignmentSubmission, AssignmentSubmissionAttempt
from apps.homework.selectors import get_submission_detail
from apps.homework.services.publication import publish_assignment
from apps.homework.services.submissions import submit_assignment_work

from apps.workspaces.models import Workspace

from apps.academics.models import Subject
from apps.academics.services import assign_subject_to_student

from apps.students.models import Student

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
def enrollment(db, workspace, subject, student):
    return assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        level="Beginner",
    )


@pytest.fixture
def deadline():
    return timezone.now() + timedelta(days=7)


def create_submission(*, workspace, subject, student, deadline):
    from apps.homework.models import Assignment

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

    recipient = assignment.recipients.get(student=student)

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="First solution",
        recorded_by=workspace.owner
    )

    submission = AssignmentSubmission.objects.get(recipient=recipient)

    return assignment, recipient, submission


def test_submission_detail_requires_authentication(client, workspace, subject, student, enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    assert response.status_code == 302


def test_get_submission_detail(workspace, subject, student, enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    result = get_submission_detail(
        workspace=workspace,
        submission_id=submission.id
    )

    assert result.id == submission.id
    assert result.recipient == recipient
    assert result.recipient.student == student

    assert result.recipient.assignment == assignment


def test_submission_selector_rejects_foreign_workspace(workspace, subject, student,  enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign-review@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    with pytest.raises(AssignmentSubmission.DoesNotExist):
        get_submission_detail(
            workspace=foreign_workspace,
            submission_id=submission.id
        )


def test_submission_detail_orders_attempts_newest_first(workspace,subject, student, enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Second solution",
        recorded_by=workspace.owner
    )

    result = get_submission_detail(
        workspace=workspace,
        submission_id=submission.id
    )

    revisions = [
        attempt.revision
        for attempt in result.ordered_attempts
    ]

    assert revisions == [2, 1]


def test_teacher_can_open_submission_detail(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    content = response.content.decode()

    assert response.status_code == 200

    assert "Submission Review" in content
    assert "Python Functions" in content
    assert "First solution" in content

    assert student.first_name in content


def test_submission_detail_shows_latest_revision_first(client,  workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    submit_assignment_work(
        workspace=workspace,
        recipient_id=recipient.id,
        answer_text="Second solution",
        recorded_by=workspace.owner
    )

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    content = response.content.decode()

    assert "Revision 2" in content
    assert "Revision 1" in content

    assert  content.index("Revision 2") < content.index("Revision 1")


def test_teacher_cannot_open_foreign_submission(client, workspace, subject, student, enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign-view@example.com",
        password="TestPassword123!"
    )

    Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    client.force_login(foreign_teacher)

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    assert response.status_code == 404


def test_teacher_can_review_submission_from_detail_page(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={
            "teacher_feedback": (
                "Good work. Improve task 3."
            )
        }
    )

    assert response.status_code == 302

    submission.refresh_from_db()

    assert submission.status  == AssignmentSubmission.Status.REVIEWED

    assert submission.teacher_feedback == "Good work. Improve task 3."

    assert  submission.reviewed_by == workspace.owner

    assert submission.reviewed_at is not None

    assert response.url == reverse(
        "homework:submission-detail",
        kwargs={"submission_id": submission.id})


def test_reviewed_submission_shows_feedback_instead_of_form(client, workspace, subject, student,  enrollment,deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": "Well done."}
    )

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    content = response.content.decode()

    assert response.status_code == 200

    assert "Well done." in content
    assert "Mark as reviewed" not in content


def test_reviewed_submission_cannot_be_reviewed_again_via_ui(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    url = reverse(
        "homework:submission-detail",
        kwargs={"submission_id": submission.id}
    )

    first_response = client.post(url,
        data={"teacher_feedback": "First review."}
    )

    assert first_response.status_code == 302

    second_response = client.post(url,
        data={"teacher_feedback": "Overwrite attempt."}
    )

    assert second_response.status_code == 200

    submission.refresh_from_db()

    assert submission.teacher_feedback == "First review."


def test_teacher_cannot_review_foreign_submission(client, workspace, subject, student, enrollment, deadline):
    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign-post@example.com",
        password="TestPassword123!"
    )

    Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    client.force_login(foreign_teacher)

    response = client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": "Hacked review"}
    )

    assert response.status_code == 404

    submission.refresh_from_db()

    assert submission.status == AssignmentSubmission.Status.SUBMITTED

    assert submission.reviewed_at is None
    assert submission.reviewed_by is None


def test_assignment_detail_shows_reviewed_after_review(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": "Good work."}
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": assignment.id}
        )
    )

    content = response.content.decode()

    assert response.status_code == 200
    assert "Reviewed" in content


def test_review_does_not_change_submission_attempts(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    attempts_before = (
        AssignmentSubmissionAttempt.objects
        .filter(submission=submission)
        .count()
    )

    client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": "Reviewed."}
    )

    attempts_after = (
        AssignmentSubmissionAttempt.objects
        .filter(submission=submission).count())

    assert attempts_after == attempts_before


def test_submission_review_post_requires_csrf(workspace, subject, student, enrollment, deadline):
    client = Client(enforce_csrf_checks=True)

    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": "Reviewed."}
    )

    assert response.status_code == 403

    submission.refresh_from_db()

    assert submission.status == AssignmentSubmission.Status.SUBMITTED

    assert submission.reviewed_at is None



def test_submission_detail_get_does_not_modify_submission(client, workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.get(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        )
    )

    assert response.status_code == 200

    submission.refresh_from_db()

    assert submission.status  == AssignmentSubmission.Status.SUBMITTED
    

    assert submission.reviewed_at is None
    assert submission.reviewed_by is None


def test_teacher_can_review_without_feedback(client,workspace, subject, student, enrollment, deadline):
    client.force_login(workspace.owner)

    assignment, recipient, submission = (
        create_submission(
            workspace=workspace,
            subject=subject,
            student=student,
            deadline=deadline
        )
    )

    response = client.post(
        reverse(
            "homework:submission-detail",
            kwargs={"submission_id": submission.id}
        ),
        data={"teacher_feedback": ""}
    )

    assert response.status_code == 302

    submission.refresh_from_db()

    assert submission.status == AssignmentSubmission.Status.REVIEWED

    assert submission.teacher_feedback == ""

    assert submission.reviewed_at is not None

    assert submission.reviewed_by == workspace.owner
    