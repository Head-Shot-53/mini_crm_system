import pytest

from django.contrib.auth import get_user_model

from apps.academics.models import Subject, StudentSubject

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.fixture
def teacher(db):
    User = get_user_model()

    return User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )


@pytest.fixture
def workspace(teacher):
    return Workspace.objects.create(
        owner=teacher,
        name="Main Workspace"
    )


@pytest.fixture
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(
        workspace=workspace,
        name="Python"
    )


@pytest.fixture
def enrollment(student, subject):
    return StudentSubject.objects.create(
        student=student,
        subject=subject
    )


@pytest.fixture
def foreign_workspace(db):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )


@pytest.fixture
def foreign_student(foreign_workspace):
    return Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )


@pytest.fixture
def foreign_subject(foreign_workspace):
    return Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )


@pytest.fixture
def foreign_enrollment(foreign_student, foreign_subject):
    return StudentSubject.objects.create(
        student=foreign_student,
        subject=foreign_subject
    )