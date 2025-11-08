from datetime import timedelta

import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Subject, Group, GroupMembership, StudentSubject
from apps.academics.services import assign_subject_to_student

from apps.homework.models import  Assignment, AssignmentRecipient, AssignmentSubmission

from apps.students.models import Student
from apps.workspaces.models import Workspace

from apps.homework.services.reviews import review_submission

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


def create_group(*, workspace, subject, name="Python Beginners"):
    return Group.objects.create(
        workspace=workspace,
        subject=subject,
        name=name,
        max_students=10,
        is_active=True
    )


def create_second_student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Petrenko",
        status=Student.Status.ACTIVE
    )

def login_teacher(client, workspace):
    client.force_login(workspace.owner)


def datetime_local(value):
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")


def create_foreign_workspace():
    User = get_user_model()

    teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Foreign Workspace"
    )

    subject = Subject.objects.create(
        workspace=workspace,
        name="English"
    )

    student = Student.objects.create(
        workspace=workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    return workspace, subject, student


def test_assignment_list_requires_authentication(client):
    response = client.get(reverse("homework:assignment-list"))

    assert response.status_code == 302


def test_assignment_list_shows_only_current_workspace(client, workspace, subject, student):
    login_teacher(client, workspace)

    Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Own Homework"
    )

    foreign_workspace, foreign_subject, foreign_student = create_foreign_workspace()

    Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Homework"
    )

    response = client.get(reverse("homework:assignment-list"))

    assert response.status_code == 200

    content = response.content.decode()

    assert "Own Homework" in content
    assert "Foreign Homework" not in content


def test_create_individual_assignment_draft(client, workspace, subject, student, deadline):
    login_teacher(client, workspace)

    response = client.post(
        reverse(
            "homework:assignment-individual-create"
        ),
        data={
            "subject": subject.id,
            "student": student.id,
            "title": "Python Functions",
            "description": "Complete exercises 1-10.",
            "due_at": datetime_local(deadline),
            "lesson": ""
        }
    )

    assignment = Assignment.objects.get(title="Python Functions")

    assert response.status_code == 302

    assert assignment.workspace == workspace
    assert assignment.subject == subject
    assert assignment.student == student
    assert assignment.group is None

    assert assignment.status == Assignment.Status.DRAFT



def test_individual_assignment_cannot_use_foreign_student(client, workspace, subject, deadline):
    login_teacher(client, workspace)
    
    foreign_workspace, foreign_subject, foreign_student = create_foreign_workspace()

    response = client.post(
        reverse(
            "homework:assignment-individual-create"
        ),
        data={
            "subject": subject.id,
            "student": foreign_student.id,
            "title": "Invalid Homework",
            "description": "",
            "due_at": datetime_local(deadline),
            "lesson": ""
        },
    )

    assert response.status_code == 200

    assert not Assignment.objects.filter(
        workspace=workspace,
        title="Invalid Homework"
    ).exists()


def test_assignment_detail_returns_404_for_foreign_workspace(client, workspace):
    login_teacher(client, workspace)

    foreign_workspace, foreign_subject, foreign_student = create_foreign_workspace()

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Homework"
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": foreign_assignment.id}
        )
    )

    assert response.status_code == 404


def test_teacher_can_edit_draft_assignment(client,workspace, subject, student, deadline):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Old title",
        description="Old description",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-edit",
            kwargs={"assignment_id": assignment.id}
        ),
        data={
            "subject": subject.id,
            "student": student.id,
            "title": "Updated title",
            "description": "Updated description",
            "due_at": datetime_local(deadline + timedelta(days=1)),
            "lesson": "",
        }
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert assignment.title == "Updated title"

    assert assignment.description == "Updated description"


def test_published_assignment_cannot_be_edited(client,workspace, subject, student, deadline):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Published Homework",
        due_at=deadline,
        status=Assignment.Status.PUBLISHED,
        published_at=timezone.now()
    )

    response = client.get(
        reverse(
            "homework:assignment-edit",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 302

    assert response.url == reverse(
        "homework:assignment-detail",
        kwargs={"assignment_id": assignment.id}
    )


def test_publish_assignment_requires_post(client, workspace, subject, student, deadline):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    response = client.get(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 405

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.DRAFT


def test_publish_individual_assignment_creates_recipient(client, workspace, subject, student, enrollment, deadline):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Homework",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert assignment.status == Assignment.Status.PUBLISHED

    assert assignment.published_at is not None

    recipient = AssignmentRecipient.objects.get(assignment=assignment)

    assert recipient.student == student


def create_published_assignment(*, workspace, subject,  student):
    now = timezone.now()

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Published Homework",
        status=Assignment.Status.PUBLISHED,
        published_at=now,
        due_at=now + timedelta(days=7)
    )

    recipient = AssignmentRecipient.objects.create(
        assignment=assignment,
        student=student,
        assigned_at=now
    )

    return assignment, recipient


def test_assignment_detail_shows_not_submitted(client, workspace, subject, student):
    login_teacher(client, workspace)

    assignment, recipient = (
        create_published_assignment(
            workspace=workspace,
            subject=subject,
            student=student
        )
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 200

    assert "Not Submitted" in (
        response.content.decode()
    )


def test_assignment_detail_shows_submitted(client, workspace, subject, student):
    login_teacher(client, workspace)

    assignment, recipient = (
        create_published_assignment(
            workspace=workspace,
            subject=subject,
            student=student
        )
    )

    now = timezone.now()

    AssignmentSubmission.objects.create(
        recipient=recipient,
        status=AssignmentSubmission.Status.SUBMITTED,
        first_submitted_at=now,
        last_submitted_at=now,
        is_late=False
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": assignment.id}
        )
    )

    content = response.content.decode()

    assert response.status_code == 200
    assert "Submitted" in content


def test_assignment_detail_shows_late(client, workspace, subject, student):
    login_teacher(client, workspace)

    assignment, recipient = (
        create_published_assignment(
            workspace=workspace,
            subject=subject,
            student=student
        )
    )

    now = timezone.now()

    AssignmentSubmission.objects.create(
        recipient=recipient,
        status=AssignmentSubmission.Status.SUBMITTED,
        first_submitted_at=now,
        last_submitted_at=now,
        is_late=True
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 200

    assert "Late" in response.content.decode()


def test_assignment_detail_shows_reviewed(client, workspace, subject, student):
    login_teacher(client, workspace)

    assignment, recipient = (
        create_published_assignment(
            workspace=workspace,
            subject=subject,
            student=student
        )
    )

    now = timezone.now()

    submission = AssignmentSubmission.objects.create(
        recipient=recipient,
        status=AssignmentSubmission.Status.SUBMITTED,
        first_submitted_at=now,
        last_submitted_at=now,
        is_late=True
    )

    review_submission(
        workspace=workspace,
        submission_id=submission.id,
        reviewed_by=workspace.owner,
        teacher_feedback="Good work."
    )

    response = client.get(
        reverse(
            "homework:assignment-detail",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 200

    content = response.content.decode()

    assert "Reviewed" in content


def test_create_group_assignment_draft(client, workspace, subject, deadline):
    login_teacher(client, workspace)

    group = create_group(
        workspace=workspace,
        subject=subject
    )

    response = client.post(
        reverse("homework:assignment-group-create"),
        data={
            "subject": subject.id,
            "group": group.id,
            "title": "Group Python Homework",
            "description": "Complete group exercises.",
            "due_at": datetime_local(deadline),
            "lesson": ""
        },
    )

    assignment = Assignment.objects.get(title="Group Python Homework")

    assert response.status_code == 302

    assert assignment.workspace == workspace
    assert assignment.subject == subject
    assert assignment.group == group
    assert assignment.student is None

    assert  assignment.status  == Assignment.Status.DRAFT


def test_group_assignment_cannot_use_foreign_group(client, workspace, subject, deadline):
    login_teacher(client, workspace)

    foreign_workspace, foreign_subject, foreign_student = create_foreign_workspace()

    foreign_group = create_group(
        workspace=foreign_workspace,
        subject=foreign_subject,
        name="Foreign Group"
    )

    response = client.post(
        reverse("homework:assignment-group-create"),
        data={
            "subject": subject.id,
            "group": foreign_group.id,
            "title": "Invalid Group Homework",
            "description": "",
            "due_at": datetime_local(deadline),
            "lesson": ""
        },
    )

    assert response.status_code == 200

    assert not Assignment.objects.filter(
        workspace=workspace,
        title="Invalid Group Homework"
    ).exists()


def test_teacher_can_edit_group_assignment_draft(client, workspace, subject, deadline):
    login_teacher(client, workspace)

    group = create_group(
        workspace=workspace,
        subject=subject
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Old Group Homework",
        description="Old description",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-edit",
            kwargs={"assignment_id": assignment.id}
        ),
        data={
            "subject": subject.id,
            "group": group.id,
            "title": "Updated Group Homework",
            "description": "Updated description",
            "due_at": datetime_local(deadline + timedelta(days=1)),
            "lesson": ""
        }
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert  assignment.title == "Updated Group Homework"


    assert assignment.description == "Updated description"
    

    assert assignment.group == group
    assert assignment.student is None


def test_publish_group_assignment_creates_recipients(client, workspace, subject, student, enrollment, deadline):
    login_teacher(client, workspace)

    group = create_group(
        workspace=workspace,
        subject=subject
    )

    second_student = create_second_student(workspace)

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    GroupMembership.objects.create(
        group=group,
        student=student
    )

    GroupMembership.objects.create(
        group=group,
        student=second_student
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Group Homework",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert assignment.status == Assignment.Status.PUBLISHED
    

    recipients = AssignmentRecipient.objects.filter(assignment=assignment)

    assert recipients.count() == 2

    assert recipients.filter(student=student).exists()

    assert recipients.filter(student=second_student).exists()


def test_publish_group_assignment_ignores_student_who_left_group(client, workspace, subject, student, enrollment, deadline):
    login_teacher(client, workspace)

    group = create_group(
        workspace=workspace,
        subject=subject
    )

    second_student = create_second_student(workspace)

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    GroupMembership.objects.create(
        group=group,
        student=student
    )

    GroupMembership.objects.create(
        group=group,
        student=second_student,
        joined_at=timezone.now() - timedelta(days=10),
        left_at=timezone.now() - timedelta(days=1)
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Group Homework",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert response.status_code == 302

    recipients = AssignmentRecipient.objects.filter(assignment=assignment)

    assert recipients.count() == 1

    assert recipients.filter(student=student).exists()

    assert not recipients.filter(student=second_student).exists()


def test_group_assignment_recipients_are_snapshot(client, workspace, subject, student, enrollment, deadline):
    login_teacher(client, workspace)

    group = create_group(
        workspace=workspace,
        subject=subject
    )

    membership = GroupMembership.objects.create(
        group=group,
        student=student
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Snapshot Homework",
        due_at=deadline
    )

    client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assert AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=student
    ).exists()

    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])

    assert AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=student
    ).exists()


def test_teacher_can_create_draft_without_deadline(client, workspace, subject, student):
    login_teacher(client, workspace)

    response = client.post(
        reverse(
            "homework:assignment-individual-create"
        ),
        data={
            "subject": subject.id,
            "student": student.id,
            "title": "Homework without deadline",
            "description": "",
            "due_at": "",
            "lesson": ""
        },
    )

    assert response.status_code == 302

    assignment = Assignment.objects.get(title="Homework without deadline")

    assert assignment.due_at is None

    assert assignment.status  == Assignment.Status.DRAFT



def test_cannot_publish_assignment_without_deadline(client, workspace,subject, student, enrollment):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=None
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert  assignment.status == Assignment.Status.DRAFT


    assert assignment.published_at is None

    assert not AssignmentRecipient.objects.filter(
        assignment=assignment
    ).exists()


def test_cannot_publish_assignment_with_past_deadline(client, workspace, subject, student, enrollment):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Expired Homework",
        due_at=timezone.now()  - timedelta(hours=1),
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": assignment.id}
        )
    )

    assignment.refresh_from_db()

    assert response.status_code == 302

    assert assignment.status == Assignment.Status.DRAFT


    assert assignment.published_at is None


def test_published_assignment_cannot_be_published_again(client, workspace, subject, student, enrollment, deadline):
    login_teacher(client, workspace)

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    publish_url = reverse(
        "homework:assignment-publish",
        kwargs={"assignment_id": assignment.id}
    )

    first_response = client.post(publish_url)

    assert first_response.status_code == 302

    recipients_before = (
        AssignmentRecipient.objects
        .filter(
            assignment=assignment
        )
        .count()
    )

    second_response = client.post(publish_url)

    assert second_response.status_code == 302

    recipients_after = (
        AssignmentRecipient.objects
        .filter(
            assignment=assignment
        )
        .count()
    )

    assert recipients_after == recipients_before



def test_teacher_cannot_publish_foreign_assignment(client, workspace, deadline):
    login_teacher(client, workspace)

    foreign_workspace, foreign_subject, foreign_student = create_foreign_workspace()

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Homework",
        due_at=deadline
    )

    response = client.post(
        reverse(
            "homework:assignment-publish",
            kwargs={"assignment_id": foreign_assignment.id}
        )
    )

    assert response.status_code == 404

    foreign_assignment.refresh_from_db()

    assert foreign_assignment.status == Assignment.Status.DRAFT
    

    assert foreign_assignment.published_at is None

    assert not AssignmentRecipient.objects.filter(
        assignment=foreign_assignment
    ).exists()