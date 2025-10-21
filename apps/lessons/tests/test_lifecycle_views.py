import pytest

from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.lessons.models import Lesson
from apps.lessons.services.creation import create_individual_lesson

from apps.academics.models import Subject

from apps.students.models import Student

from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


def test_cancel_lesson_view(client, workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    client.force_login(workspace.owner)

    response = client.post(
        reverse(
            "lessons:lesson_status",
            kwargs={
                "lesson_id": lesson.id,
                "action": "cancel"
            }
        ),
        {
            "cancellation_reason": (
                "Student requested cancellation."
            )
        }
    )

    assert response.status_code == 302

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.CANCELLED
    )

    assert lesson.cancellation_reason == (
        "Student requested cancellation."
    )


@pytest.mark.parametrize(
    "action",
    [
        "complete",
        "cancel",
    ],
)
def test_lesson_status_requires_post(client, workspace, student, subject, enrollment, lesson_time, action):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    client.force_login(
        workspace.owner
    )

    response = client.get(
        reverse(
            "lessons:lesson_status",
            kwargs={
                "lesson_id": lesson.id,
                "action": action
            }
        )
    )

    assert response.status_code == 405

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.SCHEDULED
    )


def test_lesson_cancellation_requires_csrf(workspace,student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    csrf_client = Client(enforce_csrf_checks=True)

    csrf_client.force_login(workspace.owner)

    response = csrf_client.post(
        reverse(
            "lessons:lesson_status",
            kwargs={
                "lesson_id": lesson.id,
                "action": "cancel"
            }
        )
    )

    assert response.status_code == 403

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.SCHEDULED
    )


@pytest.mark.parametrize(
    "action",
    [
        "complete",
        "cancel",
    ],
)
def test_cannot_change_foreign_lesson_status(client, workspace, lesson_time, action):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_student = Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    start_at, end_at = lesson_time

    foreign_lesson = Lesson.objects.create(
        workspace=foreign_workspace,
        student=foreign_student,
        subject=foreign_subject,
        start_at=start_at,
        end_at=end_at
    )

    client.force_login(workspace.owner)

    response = client.post(
        reverse(
            "lessons:lesson_status",
            kwargs={
                "lesson_id": foreign_lesson.id,
                "action": action
            }
        )
    )

    assert response.status_code == 404

    foreign_lesson.refresh_from_db()

    assert foreign_lesson.status == (
        Lesson.Status.SCHEDULED
    )