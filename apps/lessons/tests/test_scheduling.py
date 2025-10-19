from datetime import timedelta

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.lessons.models import Lesson

from apps.lessons.selectors import get_schedule_conflicts

from apps.lessons.services.creation import create_group_lesson, create_individual_lesson

from apps.lessons.services.rescheduling import reschedule_lesson


pytestmark = pytest.mark.django_db


def test_schedule_without_conflict(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    conflicts = get_schedule_conflicts(
        workspace=workspace,
        start_at=end_at,
        end_at=end_at + timedelta(hours=1)
    )

    assert lesson.id is not None
    assert not conflicts.exists()


def test_individual_lessons_cannot_overlap(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    overlapping_start = start_at + timedelta(
        minutes=30
    )

    overlapping_end = end_at + timedelta(
        minutes=30
    )

    with pytest.raises(ValidationError):
        create_individual_lesson(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
            start_at=overlapping_start,
            end_at=overlapping_end
        )

    assert Lesson.objects.count() == 1


def test_individual_and_group_lessons_cannot_overlap(workspace, student, subject, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    with pytest.raises(ValidationError):
        create_group_lesson(
            workspace=workspace,
            group_id=group.id,
            start_at=start_at,
            end_at=end_at
        )

    assert Lesson.objects.count() == 1


def test_adjacent_lessons_are_allowed(workspace, student, subject, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    first_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    second_lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=end_at,
        end_at=end_at + timedelta(hours=1)
    )

    assert first_lesson.id != second_lesson.id
    assert Lesson.objects.count() == 2


def test_cancelled_lesson_releases_time_slot(workspace, student, subject, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    first_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    Lesson.objects.filter(
        id=first_lesson.id
    ).update(
        status=Lesson.Status.CANCELLED
    )

    second_lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=start_at,
        end_at=end_at
    )

    assert second_lesson.id is not None
    assert Lesson.objects.count() == 2


def test_reschedule_lesson(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    new_start = start_at + timedelta(hours=2)

    new_end = new_start + timedelta(hours=1)

    updated = reschedule_lesson(
        workspace=workspace,
        lesson_id=lesson.id,
        start_at=new_start,
        end_at=new_end
    )

    assert updated.start_at == new_start
    assert updated.end_at == new_end


def test_cannot_reschedule_to_occupied_slot(workspace, student, subject, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    first_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    second_start = start_at + timedelta(hours=2)

    second_end = second_start + timedelta(hours=1)

    second_lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=second_start,
        end_at=second_end
    )

    with pytest.raises(ValidationError):
        reschedule_lesson(
            workspace=workspace,
            lesson_id=second_lesson.id,
            start_at=start_at,
            end_at=end_at
        )

    second_lesson.refresh_from_db()

    assert second_lesson.start_at == second_start
    assert second_lesson.end_at == second_end

    assert first_lesson.start_at == start_at


def test_completed_lesson_cannot_be_rescheduled(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    Lesson.objects.filter(
        id=lesson.id
    ).update(
        status=Lesson.Status.COMPLETED
    )

    with pytest.raises(ValidationError):
        reschedule_lesson(
            workspace=workspace,
            lesson_id=lesson.id,
            start_at=start_at + timedelta(days=1),
            end_at=end_at + timedelta(days=1)
        )

    lesson.refresh_from_db()

    assert lesson.start_at == start_at