import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.academics.models import Subject, StudentSubject
from apps.academics.services import assign_subject_to_student
from apps.students.models import Student
from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    User = get_user_model()

    teacher = User.objects.create_user(email="teacher@example.com",password="TestPassword123!")

    return Workspace.objects.create(owner=teacher,name="Test Teaching")


@pytest.fixture
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska",
    )


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(workspace=workspace,name="Python")


def test_assign_subject_to_student(workspace,student,subject):
    enrollment = assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        level="Beginner",
    )

    assert enrollment.student == student
    assert enrollment.subject == subject
    assert enrollment.level == "Beginner"
    assert enrollment.status == StudentSubject.Status.ACTIVE

    assert student.subjects.filter(id=subject.id).exists()


def test_cannot_assign_duplicate_subject(workspace,student,subject,):
    assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
    )

    with pytest.raises(ValidationError):
        assign_subject_to_student(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
        )


def test_database_prevents_duplicate_assignment(student,subject):
    StudentSubject.objects.create(student=student,subject=subject)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentSubject.objects.create(
                student=student,
                subject=subject,
            )


def test_cannot_assign_subject_from_another_workspace(workspace,student):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace",
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English",
    )

    with pytest.raises(Subject.DoesNotExist):
        assign_subject_to_student(
            workspace=workspace,
            student_id=student.id,
            subject_id=foreign_subject.id,
        )

    assert StudentSubject.objects.count() == 0


def test_model_validation_rejects_cross_workspace_assignment(workspace,student):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="third@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Third Workspace",
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="SQL",
    )

    enrollment = StudentSubject(
        student=student,
        subject=foreign_subject,
    )

    with pytest.raises(ValidationError):
        enrollment.full_clean()


def test_cannot_assign_subject_to_archived_student(workspace,student,subject):
    student.status = Student.Status.ARCHIVED
    student.save(update_fields=["status"])

    with pytest.raises(ValidationError):
        assign_subject_to_student(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
        )


def test_cannot_assign_inactive_subject(workspace,student,subject):
    subject.is_active = False
    subject.save(update_fields=["is_active"])

    with pytest.raises(Subject.DoesNotExist):
        assign_subject_to_student(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
        )