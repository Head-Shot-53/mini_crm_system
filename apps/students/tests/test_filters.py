import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.academics.models import Subject, StudentSubject
from apps.students.models import Student
from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def teacher():
    User = get_user_model()

    return User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )


@pytest.fixture
def workspace(teacher):
    return Workspace.objects.create(
        owner=teacher,
        name="Test Teaching"
    )


@pytest.fixture
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska",
        email="anna@example.com",
        phone="+48123456789"
    )


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(workspace=workspace, name="Python")


@pytest.mark.parametrize(
    "query",
    [
        "Anna",
        "Kowalska",
        "anna@example.com",
        "+48123456789",
        "Anna Kowalska",
        "Kowalska Anna",
    ],
)
def test_search_student(client, teacher, student, query):
    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "q": query
        }
    )

    assert response.status_code == 200

    assert student in response.context["page_obj"].object_list


def test_filter_by_status(client, teacher, workspace, student):
    paused_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov",
        status=Student.Status.PAUSED
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "status": Student.Status.PAUSED
        }
    )

    results = list(response.context["page_obj"].object_list)

    assert paused_student in results

    assert student not in results


def test_filter_by_subject(client, teacher, workspace, student, subject):
    another_student = Student.objects.create(
        workspace=workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    StudentSubject.objects.create(student=student, subject=subject)

    client.force_login(teacher)

    response = client.get(
        reverse("students:student_list"),
        {
            "subject": str(subject.id)
        }
    )

    results = list(response.context["page_obj"].object_list)

    assert student in results

    assert another_student not in results


def test_cannot_search_foreign_students(client, teacher, workspace, student):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace"
    )

    foreign_student = Student.objects.create(
        workspace=another_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "q": "Maria"
        }
    )

    results = list(response.context["page_obj"].object_list)

    assert foreign_student not in results

    assert response.context["page_obj"].paginator.count == 0


def test_cannot_filter_by_foreign_subject(client, teacher, student):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English"
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "subject": str(foreign_subject.id)
        }
    )

    assert response.status_code == 200

    assert not response.context["filter_form"].is_valid()

    assert response.context["page_obj"].paginator.count == 0


def test_student_pagination(client, teacher, workspace):
    Student.objects.bulk_create(
        [
            Student(
                workspace=workspace,
                first_name=f"Student{i:02d}",
                last_name="Test"
            )
            for i in range(23)
        ]
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"))

    page_obj = response.context["page_obj"]

    assert response.status_code == 200

    assert page_obj.paginator.count == 23

    assert page_obj.paginator.num_pages == 3

    assert len(page_obj.object_list) == 10


def test_last_page(client, teacher, workspace):
    Student.objects.bulk_create(
        [
            Student(
                workspace=workspace,
                first_name=f"Student{i:02d}",
                last_name="Test"
            )
            for i in range(23)
        ]
    )

    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "page": "3"
        }
    )

    page_obj = response.context["page_obj"]

    assert page_obj.number == 3

    assert len(page_obj.object_list) == 3

    assert not page_obj.has_next()


def test_invalid_page_number(client, teacher, workspace, student):
    client.force_login(teacher)

    response = client.get(reverse("students:student_list"),
        {
            "page": "invalid"
        }
    )

    assert response.status_code == 200

    assert response.context["page_obj"].number == 1


def test_pagination_preserves_filters(client, teacher, workspace):
    Student.objects.bulk_create(
        [
            Student(
                workspace=workspace,
                first_name=f"Student{i:02d}",
                last_name="Test"
            )
            for i in range(15)
        ]
    )

    client.force_login(teacher)

    response = client.get(
        reverse("students:student_list"),
        {
            "q": "Student",
            "status": Student.Status.ACTIVE,
            "page": "2"
        }
    )

    assert response.status_code == 200

    assert response.context["page_obj"].number == 2

    page_query = response.context["page_query"]

    assert "q=Student" in page_query

    assert "status=active" in page_query

    assert "page=" not in page_query