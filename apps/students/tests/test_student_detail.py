from datetime import date

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.academics.models import Subject, StudentSubject

from apps.academics.services import update_student_enrollment

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
        subject=subject,
        level="Beginner"
    )


def test_update_student_enrollment(workspace, student, enrollment):
    updated = update_student_enrollment(
        workspace=workspace,
        student_id=student.id,
        enrollment_id=enrollment.id,
        level="Intermediate",
        status=StudentSubject.Status.COMPLETED,
        started_on=date(2026, 9, 1),
        notes="Completed Python fundamentals."
    )

    assert updated.level == "Intermediate"

    assert updated.status == (
        StudentSubject.Status.COMPLETED
    )

    assert updated.notes == (
        "Completed Python fundamentals."
    )

    enrollment.refresh_from_db()

    assert enrollment.level == "Intermediate"


def test_invalid_enrollment_status_transition(workspace, student, enrollment):
    enrollment.status = StudentSubject.Status.COMPLETED

    enrollment.save(update_fields=["status"])

    with pytest.raises(ValidationError):
        update_student_enrollment(
            workspace=workspace,
            student_id=student.id,
            enrollment_id=enrollment.id,
            level="Advanced",
            status=StudentSubject.Status.PAUSED,
            started_on=date(2026, 9, 1),
            notes="Invalid transition attempt."
        )

    enrollment.refresh_from_db()

    assert enrollment.status == (
        StudentSubject.Status.COMPLETED
    )


def test_cannot_update_archived_student_enrollment(workspace, student, enrollment):
    student.status = Student.Status.ARCHIVED

    student.save(update_fields=["status"])

    with pytest.raises(ValidationError):
        update_student_enrollment(
            workspace=workspace,
            student_id=student.id,
            enrollment_id=enrollment.id,
            level="Advanced",
            status=StudentSubject.Status.COMPLETED,
            started_on=date(2026, 9, 1),
            notes="Should not be saved."
        )

    enrollment.refresh_from_db()

    assert enrollment.level == "Beginner"


def test_cannot_update_foreign_enrollment(workspace, student):
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

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English"
    )

    foreign_enrollment = StudentSubject.objects.create(
        student=foreign_student,
        subject=foreign_subject
    )

    with pytest.raises(StudentSubject.DoesNotExist):
        update_student_enrollment(
            workspace=workspace,
            student_id=student.id,
            enrollment_id=foreign_enrollment.id,
            level="Advanced",
            status=StudentSubject.Status.COMPLETED,
            started_on=date(2026, 9, 1),
            notes="Unauthorized update."
        )

    foreign_enrollment.refresh_from_db()

    assert foreign_enrollment.level == ""


def test_enrollment_edit_requires_authentication(client, student, enrollment):
    response = client.get(
        reverse(
            "students:enrollment_edit",
            kwargs={
                "student_id": student.id,
                "enrollment_id": enrollment.id,
            }
        )
    )

    assert response.status_code == 302


def test_enrollment_edit_view(client, teacher, student, enrollment):
    client.force_login(teacher)

    response = client.post(
        reverse(
            "students:enrollment_edit",
            kwargs={
                "student_id": student.id,
                "enrollment_id": enrollment.id
            },
        ),
        {
            "started_on": "2026-09-01",
            "level": "Intermediate",
            "status": StudentSubject.Status.COMPLETED,
            "notes": "Good progress."
        }
    )

    assert response.status_code == 302

    enrollment.refresh_from_db()

    assert enrollment.level == "Intermediate"

    assert enrollment.status == (
        StudentSubject.Status.COMPLETED
    )


def test_foreign_enrollment_edit_returns_404(client, teacher, student):
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

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English"
    )

    foreign_enrollment = StudentSubject.objects.create(
        student=foreign_student,
        subject=foreign_subject
    )

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
            "notes": "Unauthorized."
        }
    )

    assert post_response.status_code == 404

    foreign_enrollment.refresh_from_db()

    assert foreign_enrollment.level == ""


def test_archived_student_enrollment_edit_returns_403(client, teacher, student, enrollment):
    student.status = Student.Status.ARCHIVED

    student.save(
        update_fields=["status"]
    )

    client.force_login(teacher)

    url = reverse(
        "students:enrollment_edit",
        kwargs={
            "student_id": student.id,
            "enrollment_id": enrollment.id
        }
    )

    assert client.get(url).status_code == 403

    response = client.post(
        url,
        {
            "started_on": "2026-09-01",
            "level": "Advanced",
            "status": StudentSubject.Status.COMPLETED,
            "notes": "Unauthorized update."
        }
    )

    assert response.status_code == 403

    enrollment.refresh_from_db()

    assert enrollment.level == "Beginner"