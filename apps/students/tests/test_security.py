import pytest

from django.test import Client
from django.urls import reverse

from apps.academics.models import StudentSubject
from apps.students.models import Student


pytestmark = pytest.mark.django_db

@pytest.mark.parametrize(
    "view_name",
    [
        "students:student_detail",
        "students:student_edit"
    ]
)
def test_cannot_open_foreign_student(client, teacher, foreign_student, view_name):
    client.force_login(teacher)

    response = client.get(
        reverse(
            view_name,
            kwargs={
                "student_id": foreign_student.id,
            },
        )
    )

    assert response.status_code == 404


def test_cannot_update_foreign_student(client, teacher, foreign_student):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "students:student_edit",
            kwargs={
                "student_id": foreign_student.id
            }
        ),
        {
            "first_name": "Hacked",
            "last_name": "Student",
            "start_date": "2026-09-01"
        }
    )

    assert response.status_code == 404

    foreign_student.refresh_from_db()

    assert foreign_student.first_name == "Maria"
    assert foreign_student.last_name == "Nowak"


def test_cannot_archive_foreign_student(client, teacher, foreign_student):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "students:student_status",
            kwargs={
                "student_id": foreign_student.id,
                "action": "archive"
            }
        )
    )

    assert response.status_code == 404

    foreign_student.refresh_from_db()

    assert foreign_student.status == Student.Status.ACTIVE


def test_cannot_edit_foreign_enrollment(client, teacher, student, foreign_enrollment):
    client.force_login(teacher)

    url = reverse(
        "students:enrollment_edit",
        kwargs={
            "student_id": student.id,
            "enrollment_id": foreign_enrollment.id
        }
    )

    get_response = client.get(url)

    assert get_response.status_code == 404

    post_response = client.post(
        url,
        {
            "started_on": "2026-09-01",
            "level": "Advanced",
            "status": StudentSubject.Status.COMPLETED,
            "notes": "Unauthorized update."
        }
    )

    assert post_response.status_code == 404

    foreign_enrollment.refresh_from_db()

    assert foreign_enrollment.level == ""


def test_student_creation_ignores_protected_fields(client, teacher, workspace, foreign_workspace):
    client.force_login(teacher)

    response = client.post(
        reverse("students:student_create"),
        {
            "first_name": "Test",
            "last_name": "Student",
            "start_date": "2026-09-01",
            "workspace": str(foreign_workspace.id),
            "status": Student.Status.ARCHIVED
        }
    )

    assert response.status_code == 302

    student = Student.objects.get(
        first_name="Test",
        last_name="Student"
    )

    assert student.workspace == workspace
    assert student.status == Student.Status.ACTIVE


def test_student_status_requires_csrf(teacher, student):
    csrf_client = Client(
        enforce_csrf_checks=True
    )

    csrf_client.force_login(teacher)

    url = reverse(
        "students:student_status",
        kwargs={
            "student_id": student.id,
            "action": "archive"
        }
    )

    response = csrf_client.post(url)

    assert response.status_code == 403

    student.refresh_from_db()

    assert student.status == Student.Status.ACTIVE


def test_student_status_accepts_valid_csrf(teacher, student):
    csrf_client = Client(
        enforce_csrf_checks=True
    )

    csrf_client.force_login(teacher)

    detail_url = reverse(
        "students:student_detail",
        kwargs={
            "student_id": student.id,
        }
    )

    response = csrf_client.get(
        detail_url
    )

    assert response.status_code == 200

    csrf_token = (
        csrf_client.cookies["csrftoken"].value
    )

    status_url = reverse(
        "students:student_status",
        kwargs={
            "student_id": student.id,
            "action": "archive"
        }
    )

    response = csrf_client.post(
        status_url,
        HTTP_X_CSRFTOKEN=csrf_token
    )

    assert response.status_code == 302

    student.refresh_from_db()

    assert student.status == Student.Status.ARCHIVED