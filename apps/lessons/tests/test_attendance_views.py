from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.lessons.models import Lesson, LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status

from apps.academics.models import Subject

from apps.students.models import Student

from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


def test_teacher_can_open_attendance_page(client, workspace, student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    client.force_login(workspace.owner)

    response = client.get(
        reverse(
            "lessons:attendance",
            kwargs={
                "lesson_id": lesson.id
            }
        )
    )

    assert response.status_code == 200

    assert response.context["is_ready"] is True

    assert response.context["stats"]["total"] == 1


def test_teacher_can_mark_attendance_through_view(client, workspace,student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    attendance = LessonAttendance.objects.get(lesson=lesson)

    client.force_login(workspace.owner)

    response = client.post(
        reverse(
            "lessons:attendance_mark",
            kwargs={
                "lesson_id": lesson.id,
                "attendance_id": attendance.id
            }
        ),
        {
            "status": LessonAttendance.Status.PRESENT,
            "notes": "Good participation."
        },
    )

    assert response.status_code == 302

    attendance.refresh_from_db()

    assert attendance.status == (
        LessonAttendance.Status.PRESENT
    )

    assert attendance.notes == "Good participation."


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

    foreign_attendance = LessonAttendance.objects.get(lesson=foreign_lesson)

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
        },
    )

    assert response.status_code == 404

    foreign_attendance.refresh_from_db()

    assert foreign_attendance.status == (
        LessonAttendance.Status.PENDING
    )