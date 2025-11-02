import pytest

from django.contrib.auth import get_user_model

from apps.academics.models import Subject
from apps.homework.models import Assignment
from apps.homework.selectors import get_workspace_assignments
from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db
def test_selector_returns_only_own_assignments():

    User = get_user_model()

    teacher_a = User.objects.create_user(
        email="teacher-a@example.com",
        password="TestPassword123!"
    )

    teacher_b = User.objects.create_user(
        email="teacher-b@example.com",
        password="TestPassword123!"
    )

    workspace_a = Workspace.objects.create(
        owner=teacher_a,
        name="Workspace A"
    )

    workspace_b = Workspace.objects.create(
        owner=teacher_b,
        name="Workspace B"
    )

    subject_a = Subject.objects.create(
        workspace=workspace_a,
        name="Python"
    )

    subject_b = Subject.objects.create(
        workspace=workspace_b,
        name="English"
    )

    student_a = Student.objects.create(
        workspace=workspace_a,
        first_name="Anna",
        last_name="Kowalska"
    )

    student_b = Student.objects.create(
        workspace=workspace_b,
        first_name="Maria",
        last_name="Nowak"
    )

    assignment_a = Assignment.objects.create(
        workspace=workspace_a,
        subject=subject_a,
        student=student_a,
        title="Python Practice"
    )

    Assignment.objects.create(
        workspace=workspace_b,
        subject=subject_b,
        student=student_b,
        title="English Practice"
    )

    assignments = list(get_workspace_assignments(workspace=workspace_a))

    assert assignments == [assignment_a]