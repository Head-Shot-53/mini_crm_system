import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.academics.models import Group, GroupMembership, StudentSubject, Subject

from apps.academics.services import change_group_status, join_student_to_group, leave_student_from_group, update_student_enrollment

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
        name="Test Workspace"
    )


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(
        workspace=workspace,
        name="Python"
    )


@pytest.fixture
def group(workspace, subject):
    return Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners",
        max_students=1
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
def membership(workspace, student, enrollment, group):
    return join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )


def test_paused_student_keeps_group_membership(workspace, student, membership):

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="pause"
    )

    membership.refresh_from_db()

    assert membership.is_active is True


def test_paused_student_still_occupies_capacity(workspace, subject, group, student, membership):

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="pause"
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


def test_pausing_subject_preserves_membership(workspace, student, enrollment, membership):

    update_student_enrollment(
        workspace=workspace,
        student_id=student.id,
        enrollment_id=enrollment.id,
        level="Beginner",
        status=StudentSubject.Status.PAUSED,
        started_on=enrollment.started_on,
        notes="Temporary pause."
    )

    membership.refresh_from_db()

    assert membership.is_active is True


def test_cannot_rejoin_with_paused_subject(workspace, student, enrollment, group, membership):

    update_student_enrollment(
        workspace=workspace,
        student_id=student.id,
        enrollment_id=enrollment.id,
        level="Beginner",
        status=StudentSubject.Status.PAUSED,
        started_on=enrollment.started_on,
        notes=""
    )

    leave_student_from_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    with pytest.raises(ValidationError):
        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=student.id
        )


def test_archive_closes_all_current_memberships(workspace, student, membership):

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    membership.refresh_from_db()

    assert membership.left_at is not None

    assert GroupMembership.objects.filter(
        student=student,
        left_at__isnull=True
    ).count() == 0


def test_restore_does_not_rejoin_groups(workspace, student, membership):

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="restore"
    )

    membership.refresh_from_db()

    assert membership.is_active is False

    assert GroupMembership.objects.filter(
        student=student,
        left_at__isnull=True
    ).count() == 0


def test_deactivated_group_preserves_memberships(workspace, group, membership):

    change_group_status(
        workspace=workspace,
        group_id=group.id,
        action="deactivate"
    )

    membership.refresh_from_db()

    group.refresh_from_db()

    assert group.is_active is False

    assert membership.is_active is True