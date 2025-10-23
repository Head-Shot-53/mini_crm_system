from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import (
    Lesson,
    LessonAttendance,
)


pytestmark = pytest.mark.django_db


def test_legacy_completed_lesson_is_not_backfilled_on_get(client, workspace,student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1),
        status=Lesson.Status.COMPLETED
    )

    client.force_login(
        workspace.owner
    )

    url = reverse(
        "lessons:attendance",
        kwargs={
            "lesson_id": lesson.id
        }
    )

    response = client.get(url)

    assert response.status_code == 200

    assert response.context["is_legacy"] is True

    assert not LessonAttendance.objects.filter(
        lesson=lesson,
    ).exists()

    response = client.get(url)

    assert response.status_code == 200

    assert not LessonAttendance.objects.filter(
        lesson=lesson,
    ).exists()