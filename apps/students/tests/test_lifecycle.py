import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.academics.models import Subject, StudentSubject
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
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )


def test_pause_student(workspace, student):
    result = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="pause"
    )

    assert result.status == Student.Status.PAUSED


def test_resume_student(workspace, student):
    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="pause"
    )

    result = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="resume"
    )

    assert result.status == Student.Status.ACTIVE


def test_complete_student(workspace, student):
    result = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="complete"
    )

    assert result.status == Student.Status.COMPLETED


def test_reopen_completed_student(workspace, student):
    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="complete"
    )

    result = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="reopen"
    )

    assert result.status == Student.Status.ACTIVE


@pytest.mark.parametrize("previous_status",
    [
        Student.Status.ACTIVE,
        Student.Status.PAUSED,
        Student.Status.COMPLETED
    ]
)
def test_archive_and_restore_preserves_status(workspace, student, previous_status):
    student.status = previous_status
    student.save(update_fields=["status"])

    archived = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    assert archived.status == Student.Status.ARCHIVED

    assert archived.status_before_archive == previous_status

    assert archived.archived_at is not None

    restored = change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="restore"
    )

    assert restored.status == previous_status

    assert restored.status_before_archive == ""

    assert restored.archived_at is None


def test_invalid_status_transition(workspace, student):
    with pytest.raises(ValidationError):
        change_student_status(
            workspace=workspace,
            student_id=student.id,
            action="resume"
        )

    student.refresh_from_db()

    assert student.status == Student.Status.ACTIVE


def test_cannot_restore_active_student(workspace, student):
    with pytest.raises(ValidationError):
        change_student_status(
            workspace=workspace,
            student_id=student.id,
            action="restore"
        )


def test_archiving_preserves_subject_enrollments(workspace, student):
    subject = Subject.objects.create(
        workspace=workspace,
        name="Python"
    )

    enrollment = StudentSubject.objects.create(
        student=student,
        subject=subject
    )

    change_student_status(workspace=workspace, student_id=student.id, action="archive")

    assert Student.objects.filter(id=student.id).exists()

    assert StudentSubject.objects.filter(id=enrollment.id).exists()


def test_cannot_archive_foreign_student(workspace):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Teaching"
    )

    foreign_student = Student.objects.create(
        workspace=another_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    with pytest.raises(Student.DoesNotExist):
        change_student_status(
            workspace=workspace,
            student_id=foreign_student.id,
            action="archive"
        )

    foreign_student.refresh_from_db()

    assert foreign_student.status == Student.Status.ACTIVE