import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.academics.models import Group, GroupMembership, Subject, StudentSubject

from apps.academics.services import join_student_to_group

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
        max_students=5
    )


@pytest.fixture
def foreign_workspace():
    User = get_user_model()

    teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(
        owner=teacher,
        name="Foreign Workspace"
    )


@pytest.fixture
def foreign_subject(foreign_workspace):
    return Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )


@pytest.fixture
def foreign_group(foreign_workspace, foreign_subject):
    return Group.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        name="English Beginners"
    )


@pytest.mark.parametrize("view_name", ["academics:group_list", "academics:group_create"])
def test_group_pages_require_authentication(client, view_name):
    response = client.get(
        reverse(view_name)
    )

    assert response.status_code == 302


def test_create_group(client, teacher, workspace, subject):
    client.force_login(teacher)

    response = client.post(
        reverse("academics:group_create"),
        {
            "name": "Python Advanced",
            "subject": str(subject.id),
            "description": "Advanced Python course.",
            "max_students": 8
        }
    )

    assert response.status_code == 302

    group = Group.objects.get(name="Python Advanced")

    assert group.workspace == workspace
    assert group.subject == subject
    assert group.max_students == 8


@pytest.mark.django_db
def test_cannot_create_group_with_foreign_subject(client, teacher, workspace, foreign_subject):
    client.force_login(teacher)

    response = client.post(
        reverse("academics:group_create"),
        {
            "name": "Foreign Group",
            "subject": str(foreign_subject.id),
            "max_students": 5,
        },
    )

    assert response.status_code == 200

    form = response.context["form"]

    assert not form.is_valid()
    assert "subject" in form.errors

    assert not Group.objects.filter(
        workspace=workspace,
        name="Foreign Group",
    ).exists()

    assert not Group.objects.filter(
        name="Foreign Group",
        subject=foreign_subject,
    ).exists()


def test_group_creation_ignores_foreign_workspace(client, teacher, workspace, subject, foreign_workspace):
    client.force_login(teacher)

    response = client.post(
        reverse("academics:group_create"),
        {
            "name": "Secure Group",
            "subject": str(subject.id),
            "workspace": str(foreign_workspace.id),
            "max_students": 5
        },
    )

    assert response.status_code == 302

    group = Group.objects.get(
        name="Secure Group"
    )

    assert group.workspace == workspace


def test_group_list_contains_only_own_groups(client, teacher, group, foreign_group):
    client.force_login(teacher)

    response = client.get(
        reverse("academics:group_list")
    )

    assert response.status_code == 200

    content = response.content.decode()

    assert "Python Beginners" in content
    assert "English Beginners" not in content


@pytest.mark.parametrize("view_name",["academics:group_detail", "academics:group_edit"])
def test_cannot_open_foreign_group(client, teacher, foreign_group, view_name):
    client.force_login(teacher)

    response = client.get(
        reverse(
            view_name,
            kwargs={
                "group_id": foreign_group.id
            }
        )
    )

    assert response.status_code == 404


def test_cannot_update_foreign_group(client, teacher, foreign_group):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_edit",
            kwargs={
                "group_id": foreign_group.id
            }
        ),
        {
            "name": "Unauthorized Change",
            "max_students": 10
        }
    )

    assert response.status_code == 404

    foreign_group.refresh_from_db()

    assert foreign_group.name == "English Beginners"


def test_update_group(client, teacher, group):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_edit",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "name": "Python Fundamentals",
            "description": "Updated description.",
            "max_students": 10
        }
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.name == "Python Fundamentals"
    assert group.description == "Updated description."
    assert group.max_students == 10


def test_cannot_change_group_subject_through_edit(client, teacher, group, workspace):
    another_subject = Subject.objects.create(
        workspace=workspace,
        name="Django"
    )

    original_subject_id = group.subject_id

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_edit",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "name": group.name,
            "description": group.description,
            "max_students": group.max_students,
            "subject": str(another_subject.id)
        }
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.subject_id == original_subject_id


def test_cannot_reduce_capacity_below_current_count(client, teacher, workspace, subject, group):
    for name in ("Anna", "Oleg"):
        student = Student.objects.create(
            workspace=workspace,
            first_name=name,
            last_name="Test"
        )

        StudentSubject.objects.create(
            student=student,
            subject=subject
        )

        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=student.id
        )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_edit",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "name": group.name,
            "description": group.description,
            "max_students": 1
        }
    )

    assert response.status_code == 200

    assert response.context["form"].non_field_errors()

    group.refresh_from_db()

    assert group.max_students == 5


def test_group_detail_counts_only_current_members(client, teacher, workspace, subject, group):
    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    StudentSubject.objects.create(
        student=student,
        subject=subject
    )

    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    client.force_login(teacher)

    response = client.get(
        reverse(
            "academics:group_detail",
            kwargs={
                "group_id": group.id
            }
        )
    )

    assert response.status_code == 200

    assert response.context[
        "group"
    ].active_members_count == 1

    assert response.context["available_seats"] == 4