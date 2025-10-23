from datetime import timedelta

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson, LessonAttendance

from apps.lessons.services.lifecycle import  change_lesson_status


pytestmark = pytest.mark.django_db


def test_attendance_mark_requires_csrf(workspace, student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    attendance = LessonAttendance.objects.get(lesson=lesson, student=student)

    csrf_client = Client(enforce_csrf_checks=True,)

    csrf_client.force_login(workspace.owner)

    response = csrf_client.post(
        reverse(
            "lessons:attendance_mark",
            kwargs={
                "lesson_id": lesson.id,
                "attendance_id": attendance.id
            }
        ),
        {
            "status": LessonAttendance.Status.PRESENT,
            "notes": "Unauthorized request."
        }
    )

    assert response.status_code == 403

    attendance.refresh_from_db()

    assert attendance.status == (
        LessonAttendance.Status.PENDING
    )


def test_attendance_mark_requires_post(client, workspace, student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    attendance = LessonAttendance.objects.get(lesson=lesson,)

    client.force_login(workspace.owner)

    response = client.get(
        reverse(
            "lessons:attendance_mark",
            kwargs={
                "lesson_id": lesson.id,
                "attendance_id": attendance.id
            }
        )
    )

    assert response.status_code == 405

    attendance.refresh_from_db()

    assert attendance.status == (
        LessonAttendance.Status.PENDING
    )