import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.lessons.models import Lesson


pytestmark = pytest.mark.django_db


def test_individual_lesson_model(workspace, student, subject, lesson_time):
    start_at, end_at = lesson_time

    lesson = Lesson(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    lesson.full_clean()
    lesson.save()

    assert lesson.lesson_type == "individual"
    assert lesson.group is None
    assert lesson.duration_minutes == 60
    assert lesson.status == Lesson.Status.SCHEDULED


def test_group_lesson_model(workspace, group, subject, lesson_time):
    start_at, end_at = lesson_time

    lesson = Lesson(
        workspace=workspace,
        group=group,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    lesson.full_clean()
    lesson.save()

    assert lesson.lesson_type == "group"
    assert lesson.student is None
    assert lesson.duration_minutes == 60


def test_lesson_requires_exactly_one_target(workspace, subject, lesson_time):
    start_at, end_at = lesson_time

    lesson = Lesson(
        workspace=workspace,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    with pytest.raises(ValidationError):
        lesson.full_clean()


def test_database_rejects_lesson_without_target(workspace, subject, lesson_time,):
    start_at, end_at = lesson_time

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Lesson.objects.create(
                workspace=workspace,
                subject=subject,
                start_at=start_at,
                end_at=end_at
            )


def test_database_rejects_invalid_time_range(workspace, student,subject, lesson_time):
    start_at, end_at = lesson_time

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Lesson.objects.create(
                workspace=workspace,
                student=student,
                subject=subject,
                start_at=end_at,
                end_at=start_at
            )