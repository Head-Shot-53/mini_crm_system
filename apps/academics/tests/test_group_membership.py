import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.academics.models import Subject, StudentSubject, Group, GroupMembership

from apps.academics.services import join_student_to_group, leave_student_from_group

from apps.academics.selectors import get_active_group_memberships

from apps.students.models import Student
from apps.students.services.lifecycle import change_student_status

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
        name="Test Teaching"
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
    return Group.objects.create(workspace=workspace, subject=subject,
        name="Python Beginners",
        max_students=2
    )

def test_student_can_join_group(workspace, student, enrollment, group):
    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    assert membership.group == group
    assert membership.student == student
    assert membership.is_active is True

    assert GroupMembership.objects.filter(
        group=group,
        student=student,
        left_at__isnull=True
    ).count() == 1

def test_cannot_join_same_group_twice(workspace, student, enrollment, group):
    join_student_to_group(workspace=workspace, group_id=group.id, student_id=student.id)

    with pytest.raises(ValidationError):
        join_student_to_group(workspace=workspace,
            group_id=group.id,
            student_id=student.id
        )

    assert GroupMembership.objects.filter(
        group=group,
        student=student,
        left_at__isnull=True
    ).count() == 1


def test_student_needs_subject_enrollment(workspace, student, group):
    with pytest.raises(ValidationError):
        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=student.id
        )

    assert GroupMembership.objects.count() == 0


def test_group_capacity_is_enforced(workspace, subject, student, enrollment, group):
    group.max_students = 1
    group.save(
        update_fields=["max_students"]
    )

    second_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov"
    )

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    with pytest.raises(ValidationError):
        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=second_student.id
        )

    assert GroupMembership.objects.filter(
        group=group,
        left_at__isnull=True
    ).count() == 1


def test_rejoin_preserves_history(workspace, student, enrollment, group):
    first_membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    leave_student_from_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    second_membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    first_membership.refresh_from_db()

    assert first_membership.left_at is not None

    assert second_membership.is_active is True

    assert first_membership.id != second_membership.id

    assert GroupMembership.objects.filter(
        group=group,
        student=student,
    ).count() == 2


def test_cannot_join_foreign_student(workspace, group):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace"
    )

    foreign_student = Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    with pytest.raises(Student.DoesNotExist):
        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=foreign_student.id
        )


def test_archiving_student_closes_membership(workspace, student, enrollment, group):
    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    membership.refresh_from_db()

    assert membership.left_at is not None

    assert membership.is_active is False

    assert not get_active_group_memberships(
        workspace=workspace,
        group_id=group.id
    ).exists()


def test_database_prevents_duplicate_active_membership(student, group):
    GroupMembership.objects.create(
        group=group,
        student=student
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GroupMembership.objects.create(
                group=group,
                student=student
            )