from datetime import timedelta

import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.academics.models import Group, StudentSubject, Subject
from apps.students.models import Student
from apps.workspaces.models import Workspace


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
        name="Python Beginners"
    )


@pytest.fixture
def lesson_time():
    start_at = timezone.now() + timedelta(days=2)

    start_at = start_at.replace(second=0, microsecond=0)

    end_at = start_at + timedelta(minutes=60)

    return start_at, end_at