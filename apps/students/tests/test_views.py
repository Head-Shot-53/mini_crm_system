import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Subject, StudentSubject
from apps.students.models import Student
from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def teacher():
    User = get_user_model()

    return User.objects.create_user(email="teacher@example.com",password="TestPassword123!")


@pytest.fixture
def workspace(teacher):
    return Workspace.objects.create(owner=teacher, name="Test Teaching")


@pytest.fixture
def student(workspace):
    return Student.objects.create(workspace=workspace,first_name="Anna",last_name="Kowalska")


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(workspace=workspace,name="Python")


def test_student_list_requires_authentication(client):
    response = client.get(reverse("students:student_list"))

    assert response.status_code == 302


def test_student_list_contains_only_own_students(client,teacher,workspace,student):

    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Teaching",
    )

    Student.objects.create(
        workspace=another_workspace,
        first_name="Maria",
        last_name="Nowak",
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"))

    assert response.status_code == 200

    assert b"Anna Kowalska" in response.content

    assert b"Maria Nowak" not in response.content


def test_create_student(client,teacher,workspace):

    client.force_login(teacher)

    response = client.post(reverse("students:student_create"),
        {
            "first_name": "Oleg",
            "last_name": "Ivanov",
            "email": "oleg@example.com",
            "start_date": "2026-09-01",
            "default_lesson_price": "100.00",
        },
    )

    assert response.status_code == 302

    student = Student.objects.get(email="oleg@example.com")

    assert student.workspace == workspace

    assert student.full_name == "Oleg Ivanov"


@pytest.mark.django_db
def test_cannot_create_student_in_foreign_workspace(client,teacher,workspace):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Foreign Workspace",
    )

    client.force_login(teacher)

    response = client.post(
        reverse("students:student_create"),
        {
            "first_name": "Test",
            "last_name": "Student",
            "start_date": timezone.localdate().isoformat(),
            "workspace": str(another_workspace.id),
        },
    )

    assert response.status_code == 302

    student = Student.objects.get(
        first_name="Test",
        last_name="Student",
    )

    assert student.workspace_id == workspace.id

    assert student.workspace_id != another_workspace.id

    assert Student.objects.count() == 1


def test_cannot_edit_foreign_student(client,teacher):

    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Teaching",
    )

    foreign_student = Student.objects.create(
        workspace=another_workspace,
        first_name="Maria",
        last_name="Nowak",
    )

    client.force_login(teacher)

    response = client.get(
        reverse("students:student_edit",
            kwargs={
                "student_id": foreign_student.id,
            }
        )
    )

    assert response.status_code == 404


def test_assign_subject_to_student(client,teacher,student,subject):

    client.force_login(teacher)

    response = client.post(
        reverse("students:student_detail",
            kwargs={
                "student_id": student.id,
            }
        ),
        {
            "subject": str(subject.id),
            "level": "Beginner",
            "started_on": "2026-09-01",
        },
    )

    assert response.status_code == 302

    assert StudentSubject.objects.filter(
        student=student,
        subject=subject,
    ).exists()


def test_cannot_assign_foreign_subject(client,teacher,student):

    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!",
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Teaching",
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English",
    )

    client.force_login(teacher)

    response = client.post(
        reverse("students:student_detail",
            kwargs={
                "student_id": student.id,
            }
        ),
        {
            "subject": str(foreign_subject.id),
            "level": "Beginner",
        },
    )

    assert response.status_code == 200

    assert not StudentSubject.objects.filter(
        student=student,
        subject=foreign_subject,
    ).exists()