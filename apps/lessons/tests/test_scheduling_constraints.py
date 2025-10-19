from datetime import timedelta

import pytest

from django.db import IntegrityError, transaction

from apps.lessons.models import Lesson


pytestmark = pytest.mark.django_db


def test_database_rejects_overlapping_lessons(workspace, student, subject, group, lesson_time):
    start_at, end_at = lesson_time

    Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Lesson.objects.create(
                workspace=workspace,
                group=group,
                subject=subject,
                start_at=start_at + timedelta(minutes=30),
                end_at=end_at + timedelta(minutes=30)
            )

    assert Lesson.objects.count() == 1