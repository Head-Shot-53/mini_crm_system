from datetime import timedelta

import pytest

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.academics.models import Group, StudentSubject, Subject

from apps.academics.services import join_student_to_group, leave_student_from_group

from apps.homework.models import Assignment, AssignmentRecipient

from apps.homework.services.publication import publish_assignment

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
def group(workspace, subject):
    return Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners",
        max_students=10
    )


@pytest.fixture
def deadline():
    return timezone.now() + timedelta(days=7)


def test_publish_individual_assignment(workspace, subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Functions",
        due_at=deadline
    )

    published = publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    published.refresh_from_db()

    assert published.status == Assignment.Status.PUBLISHED

    assert published.published_at is not None

    recipient = AssignmentRecipient.objects.get(assignment=published)

    assert recipient.student == student

    assert recipient.group_membership is None

    assert recipient.source == AssignmentRecipient.Source.SNAPSHOT

    assert recipient.assigned_at == published.published_at


def test_publish_group_assignment_creates_snapshot(workspace, subject, student, enrollment, group, deadline):
    second_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov"
    )

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    first_membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    second_membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=second_student.id
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Python Functions",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    recipients = AssignmentRecipient.objects.filter(assignment=assignment)

    assert recipients.count() == 2

    assert set(recipients.values_list("student_id", flat=True,)) == {student.id, second_student.id}

    assert recipients.get(student=student).group_membership == first_membership

    assert recipients.get(student=second_student).group_membership == second_membership


def test_new_group_member_is_not_added_after_publication(workspace, subject, student, enrollment, group, deadline):
    join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    second_student = Student.objects.create(
        workspace=workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=second_student.id
    )

    assert AssignmentRecipient.objects.filter(assignment=assignment).count() == 1

    assert not AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=second_student
    ).exists()


def test_group_leave_preserves_assignment_recipient(workspace,subject, student, enrollment, group, deadline):
    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Homework",
        due_at=deadline
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    leave_student_from_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    membership.refresh_from_db()

    assert membership.left_at is not None

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    assert recipient.group_membership_id == membership.id


def test_assignment_cannot_be_published_twice(workspace, subject, student, enrollment, deadline):
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

    with pytest.raises(ValidationError):
        publish_assignment(
            workspace=workspace,
            assignment_id=assignment.id
        )

    assert AssignmentRecipient.objects.filter(
        assignment=assignment
    ).count() == 1


def test_assignment_without_deadline_cannot_be_published(workspace, subject, student, enrollment):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework"
    )

    with pytest.raises(ValidationError):
        publish_assignment(
            workspace=workspace,
            assignment_id=assignment.id
        )

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.DRAFT

    assert not assignment.recipients.exists()


def test_assignment_with_expired_deadline_cannot_be_published(workspace, subject, student, enrollment):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=timezone.now() - timedelta(hours=1)
    )

    with pytest.raises(ValidationError):
        publish_assignment(
            workspace=workspace,
            assignment_id=assignment.id
        )

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.DRAFT


def test_empty_group_cannot_receive_published_assignment(workspace, subject, group, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Group Homework",
        due_at=deadline
    )

    with pytest.raises(ValidationError):
        publish_assignment(
            workspace=workspace,
            assignment_id=assignment.id
        )

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.DRAFT

    assert not assignment.recipients.exists()


def test_database_prevents_duplicate_recipient(workspace, subject, student, enrollment, deadline):
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

    with pytest.raises(IntegrityError):

        with transaction.atomic():

            AssignmentRecipient.objects.create(
                assignment=assignment,
                student=student,
                assigned_at=assignment.published_at
            )

    assert AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=student
    ).count() == 1


@pytest.mark.django_db
def test_cannot_publish_assignment_from_foreign_workspace(workspace, deadline):
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

    foreign_assignment = Assignment.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        student=foreign_student,
        title="Foreign Assignment",
        description="This assignment belongs to another workspace.",
        due_at=deadline
    )

    original_status = foreign_assignment.status
    original_published_at = foreign_assignment.published_at

    with pytest.raises(Assignment.DoesNotExist):
        publish_assignment(
            workspace=workspace,
            assignment_id=foreign_assignment.id
        )

    foreign_assignment.refresh_from_db()

    assert foreign_assignment.workspace_id == foreign_workspace.id

    assert foreign_assignment.status == original_status

    assert foreign_assignment.published_at == original_published_at

    assert not AssignmentRecipient.objects.filter(
        assignment=foreign_assignment,
    ).exists()


def test_publication_rolls_back_if_recipient_creation_fails(workspace,subject, student, enrollment, deadline):
    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Homework",
        due_at=deadline
    )

    with patch(
        "apps.homework.services.publication."
        "AssignmentRecipient.objects.bulk_create",
        side_effect=RuntimeError(
            "Simulated insert failure"
        ),
    ):

        with pytest.raises(RuntimeError):

            publish_assignment(
                workspace=workspace,
                assignment_id=assignment.id
            )

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.DRAFT

    assert assignment.published_at is None

    assert not AssignmentRecipient.objects.filter(assignment=assignment).exists()