import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client

from apps.academics.models import Group, GroupMembership, Subject, StudentSubject

from apps.academics.services import join_student_to_group, leave_student_from_group

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
        max_students=2
    )


@pytest.fixture
def student(workspace, subject):
    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    StudentSubject.objects.create(
        student=student,
        subject=subject
    )

    return student


def test_join_group_through_view(client, teacher, group, student):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_join",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "student": str(student.id)
        }
    )

    assert response.status_code == 302

    assert GroupMembership.objects.filter(
        group=group,
        student=student,
        left_at__isnull=True
    ).exists()


def test_duplicate_join_is_rejected(client, teacher, workspace, group, student):
    join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_join",
            kwargs={
                "group_id": group.id
            },
        ),
        {
            "student": str(student.id)
        }
    )

    assert response.status_code == 302

    assert GroupMembership.objects.filter(
        group=group,
        student=student,
        left_at__isnull=True
    ).count() == 1


def test_leave_group_preserves_history(client, teacher, workspace, group, student):
    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_leave",
            kwargs={
                "group_id": group.id,
                "student_id": student.id
            }
        )
    )

    assert response.status_code == 302

    membership.refresh_from_db()

    assert membership.left_at is not None

    assert GroupMembership.objects.filter(
        id=membership.id
    ).exists()


def test_deactivate_group(client, teacher, group):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_status",
            kwargs={
                "group_id": group.id,
                "action": "deactivate"
            }
        )
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.is_active is False


def test_cannot_join_inactive_group(client, teacher, group, student):
    group.is_active = False
    group.save(
        update_fields=["is_active"]
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_join",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "student": str(student.id)
        }
    )

    assert response.status_code == 302

    assert not GroupMembership.objects.filter(
        group=group,
        student=student,
        left_at__isnull=True
    ).exists()


def test_activate_group(client, teacher, group):
    group.is_active = False
    group.save(
        update_fields=["is_active"]
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_status",
            kwargs={
                "group_id": group.id,
                "action": "activate"
            }
        )
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.is_active is True


def test_cannot_activate_group_with_inactive_subject(client, teacher, group, subject):
    group.is_active = False
    group.save(update_fields=["is_active"])

    subject.is_active = False
    subject.save(update_fields=["is_active"])

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_status",
            kwargs={
                "group_id": group.id,
                "action": "activate"
            }
        )
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.is_active is False


@pytest.fixture
def foreign_group():
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    return Group.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        name="English Beginners"
    )


@pytest.mark.parametrize(
    "view_name,kwargs_extra",
    [
        (
            "academics:group_join",
            {}
        ),
        (
            "academics:group_status",
            {"action": "deactivate"}
        )
    ]
)
def test_cannot_manage_foreign_group(client, teacher, foreign_group, view_name, kwargs_extra):
    client.force_login(teacher)

    response = client.post(
        reverse(
            view_name,
            kwargs={
                "group_id": foreign_group.id,
                **kwargs_extra
            }
        )
    )

    assert response.status_code == 404


def test_cannot_join_foreign_student(client, teacher, group, foreign_group):
    foreign_student = Student.objects.create(
        workspace=foreign_group.workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_join",
            kwargs={
                "group_id": group.id
            }
        ),
        {
            "student": str(foreign_student.id)
        }
    )

    assert response.status_code == 302

    assert not GroupMembership.objects.filter(
        group=group,
        student=foreign_student
    ).exists()


def test_cannot_remove_foreign_student(client, teacher, group, foreign_group):
    foreign_student = Student.objects.create(
        workspace=foreign_group.workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    client.force_login(teacher)

    response = client.post(
        reverse(
            "academics:group_leave",
            kwargs={
                "group_id": group.id,
                "student_id": foreign_student.id
            }
        )
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "view_name,kwargs_extra",
    [
        (
            "academics:group_join",
            {},
        ),
        (
            "academics:group_status",
            {"action": "deactivate"},
        ),
    ],
)
def test_group_management_requires_post(client, teacher, group, view_name, kwargs_extra):
    client.force_login(teacher)

    response = client.get(
        reverse(
            view_name,
            kwargs={
                "group_id": group.id,
                **kwargs_extra
            }
        )
    )

    assert response.status_code == 405


def test_group_detail_displays_membership_history(client, teacher, workspace, group, student):
    membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    leave_student_from_group(
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

    history = response.context["history_page"]

    assert membership.id in [
        item.id
        for item in history.object_list
    ]

    assert response.context[
        "group"
    ].active_members_count == 0


def test_group_status_requires_csrf(teacher, group):

    csrf_client = Client(enforce_csrf_checks=True)

    csrf_client.force_login(teacher)

    response = csrf_client.post(
        reverse(
            "academics:group_status",
            kwargs={
                "group_id": group.id,
                "action": "deactivate"
            }
        )
    )

    assert response.status_code == 403

    group.refresh_from_db()

    assert group.is_active is True


def test_group_status_accepts_valid_csrf(teacher, group):

    csrf_client = Client(
        enforce_csrf_checks=True,
    )

    csrf_client.force_login(teacher)

    detail_url = reverse(
        "academics:group_detail",
        kwargs={
            "group_id": group.id
        }
    )

    response = csrf_client.get(detail_url)

    assert response.status_code == 200

    token = csrf_client.cookies["csrftoken"].value

    status_url = reverse(
        "academics:group_status",
        kwargs={
            "group_id": group.id,
            "action": "deactivate"
        }
    )

    response = csrf_client.post(
        status_url,
        HTTP_X_CSRFTOKEN=token
    )

    assert response.status_code == 302

    group.refresh_from_db()

    assert group.is_active is False