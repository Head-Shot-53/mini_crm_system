from datetime import timedelta

import pytest

from django.utils import timezone

from apps.lessons.models import Lesson, LessonAttendance

from apps.lessons.selectors import get_lesson_attendance

from apps.lessons.services.lifecycle import change_lesson_status


@pytest.mark.django_db
def test_attendance_selector_avoids_n_plus_one(django_assert_num_queries, workspace, student, subject):
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

    with django_assert_num_queries(1):

        records = list(
            get_lesson_attendance(
                workspace=workspace,
                lesson=lesson
            )
        )

        for record in records:
            _ = record.student.full_name
            _ = record.recorded_by
            _ = record.group_membership

    assert len(records) == 1