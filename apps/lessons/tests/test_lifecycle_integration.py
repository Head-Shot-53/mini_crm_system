from datetime import timedelta

import pytest

from apps.academics.services import change_group_status

from apps.lessons.models import Lesson

from apps.lessons.services.creation import create_group_lesson, create_individual_lesson

from apps.students.services.lifecycle import change_student_status


pytestmark = pytest.mark.django_db


def test_archiving_student_cancels_future_lessons(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    first_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    second_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at + timedelta(days=1),
        end_at=end_at + timedelta(days=1)
    )

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    first_lesson.refresh_from_db()
    second_lesson.refresh_from_db()

    assert first_lesson.status == (
        Lesson.Status.CANCELLED
    )

    assert second_lesson.status == (
        Lesson.Status.CANCELLED
    )

    assert first_lesson.cancelled_at is not None

    assert second_lesson.cancelled_at is not None


def test_archiving_student_preserves_group_lessons(workspace, student, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    group_lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=start_at,
        end_at=end_at
    )

    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    group_lesson.refresh_from_db()

    assert group_lesson.status == (
        Lesson.Status.SCHEDULED
    )


def test_deactivating_group_preserves_lessons(workspace, group, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=start_at,
        end_at=end_at
    )

    change_group_status(
        workspace=workspace,
        group_id=group.id,
        action="deactivate"
    )

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.SCHEDULED
    )