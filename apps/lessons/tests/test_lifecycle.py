from datetime import timedelta

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.lessons.models import Lesson

from apps.lessons.services.creation import create_group_lesson, create_individual_lesson

from apps.lessons.services.lifecycle import change_lesson_status


pytestmark = pytest.mark.django_db


def test_complete_finished_lesson(workspace, student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    updated = change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    assert updated.status == (
        Lesson.Status.COMPLETED
    )

    assert updated.completed_at is not None

    assert updated.cancelled_at is None

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.COMPLETED
    )

def test_cannot_complete_future_lesson(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    with pytest.raises(ValidationError):
        change_lesson_status(
            workspace=workspace,
            lesson_id=lesson.id,
            action="complete"
        )

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.SCHEDULED
    )

    assert lesson.completed_at is None


def test_cancel_future_lesson(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    updated = change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="cancel",
        reason="Student is unavailable."
    )

    assert updated.status == (
        Lesson.Status.CANCELLED
    )

    assert updated.cancelled_at is not None

    assert updated.cancellation_reason == (
        "Student is unavailable."
    )


def test_cancelled_lesson_releases_time_slot(workspace, student, subject, enrollment, group, lesson_time):
    start_at, end_at = lesson_time

    first_lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=first_lesson.id,
        action="cancel"
    )

    second_lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=start_at,
        end_at=end_at
    )

    assert second_lesson.id is not None

    assert Lesson.objects.count() == 2

    assert Lesson.objects.filter(
        workspace=workspace,
        status=Lesson.Status.SCHEDULED,
    ).count() == 1


def test_completed_lesson_keeps_time_slot(workspace, student, subject, group):
    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    with pytest.raises(IntegrityError):

        with transaction.atomic():

            Lesson.objects.create(
                workspace=workspace,
                group=group,
                subject=subject,
                start_at=start_at,
                end_at=end_at
            )


@pytest.mark.parametrize("action",["complete", "cancel"])
def test_cancelled_lesson_is_terminal(workspace, student, subject, enrollment, lesson_time, action):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="cancel"
    )

    with pytest.raises(ValidationError):
        change_lesson_status(
            workspace=workspace,
            lesson_id=lesson.id,
            action=action
        )

    lesson.refresh_from_db()

    assert lesson.status == (
        Lesson.Status.CANCELLED
    )