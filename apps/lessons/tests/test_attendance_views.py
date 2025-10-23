from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from urllib.parse import parse_qs, urlsplit

from apps.lessons.models import Lesson, LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status

from apps.academics.models import Subject

from apps.students.models import Student

from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.mark.django_db
def test_cannot_modify_foreign_attendance(client, workspace, student, subject):
    now = timezone.now()

    own_lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=own_lesson.id,
        action="complete"
    )

    own_attendance = LessonAttendance.objects.get(lesson=own_lesson, student=student)

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

    foreign_lesson = Lesson.objects.create(
        workspace=foreign_workspace,
        student=foreign_student,
        subject=foreign_subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=foreign_workspace,
        lesson_id=foreign_lesson.id,
        action="complete"
    )

    foreign_attendance = LessonAttendance.objects.get(
        lesson=foreign_lesson,
        student=foreign_student
    )

    def get_database_snapshot():
        return {
            "lessons": list(
                Lesson.objects
                .order_by("pk")
                .values()
            ),
            "attendance": list(
                LessonAttendance.objects
                .order_by("pk")
                .values()
            )
        }

    initial_snapshot = get_database_snapshot()

    client.force_login(workspace.owner)

    response = client.post(
        reverse(
            "lessons:attendance_mark",
            kwargs={
                "lesson_id": own_lesson.id,
                "attendance_id": foreign_attendance.id
            }
        ),
        {
            "status": LessonAttendance.Status.PRESENT,
            "notes": "Unauthorized update."
        }
    )

    assert response.status_code == 404

    assert get_database_snapshot() == initial_snapshot

    response = client.post(
        reverse(
            "lessons:attendance_mark",
            kwargs={
                "lesson_id": foreign_lesson.id,
                "attendance_id": own_attendance.id
            }
        ),
        {
            "status": LessonAttendance.Status.PRESENT,
            "notes": "Attempt to modify own attendance "
                     "through foreign lesson."
        }
    )

    assert response.status_code == 404

    assert get_database_snapshot() == initial_snapshot

    response = client.get(
        reverse(
            "lessons:attendance",
            kwargs={
                "lesson_id": foreign_lesson.id
            }
        )
    )

    assert response.status_code == 404

    assert get_database_snapshot() == initial_snapshot

    client.logout()

    attendance_url = reverse(
        "lessons:attendance",
        kwargs={
            "lesson_id": own_lesson.id
        }
    )

    response = client.get(attendance_url)

    assert response.status_code == 302

    redirect = urlsplit(response["Location"])

    assert parse_qs(redirect.query).get("next") == [attendance_url]

    assert get_database_snapshot() == initial_snapshot

    attendance_mark_url = reverse(
        "lessons:attendance_mark",
        kwargs={
            "lesson_id": own_lesson.id,
            "attendance_id": own_attendance.id
        }
    )

    response = client.post(
        attendance_mark_url,
        {
            "status": LessonAttendance.Status.PRESENT,
            "notes": "Anonymous modification attempt."
        }
    )

    assert response.status_code == 302

    redirect = urlsplit(response["Location"])

    assert parse_qs(redirect.query).get("next") == [
        attendance_mark_url
    ]

    assert get_database_snapshot() == initial_snapshot

    own_lesson.refresh_from_db()
    foreign_lesson.refresh_from_db()

    own_attendance.refresh_from_db()
    foreign_attendance.refresh_from_db()

    assert own_lesson.status == Lesson.Status.COMPLETED

    assert foreign_lesson.status == Lesson.Status.COMPLETED

    assert own_attendance.status == (
        LessonAttendance.Status.PENDING
    )

    assert foreign_attendance.status == (
        LessonAttendance.Status.PENDING
    )

    assert get_database_snapshot() == initial_snapshot