from datetime import timedelta

import pytest

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.lessons.models import Lesson, LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status
from apps.lessons.services.attendance import set_lesson_attendance

from apps.academics.models import GroupMembership, StudentSubject

from apps.students.models import Student


pytestmark = pytest.mark.django_db


def test_individual_attendance_is_initialized(workspace, student, subject):
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

    lesson.refresh_from_db()

    assert lesson.status == Lesson.Status.COMPLETED

    assert lesson.attendance_initialized_at is not None

    attendance = LessonAttendance.objects.get(
        lesson=lesson
    )

    assert attendance.student == student

    assert attendance.status == (
        LessonAttendance.Status.PENDING
    )

    assert attendance.group_membership is None


def test_group_attendance_snapshot(workspace, student, subject, group, enrollment):
    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    first_membership = GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=start_at - timedelta(days=1)
    )

    second_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov"
    )

    StudentSubject.objects.create(
        student=second_student,
        subject=subject
    )

    second_membership = GroupMembership.objects.create(
        group=group,
        student=second_student,
        joined_at=start_at - timedelta(days=1)
    )

    lesson = Lesson.objects.create(
        workspace=workspace,
        group=group,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    records = LessonAttendance.objects.filter(lesson=lesson)

    assert records.count() == 2

    assert set(records.values_list("student_id", flat=True)) == {student.id, second_student.id}

    assert records.get(
        student=student
    ).group_membership == first_membership

    assert records.get(
        student=second_student
    ).group_membership == second_membership


def test_student_joined_after_lesson_start_is_excluded(workspace, student, subject, group, enrollment):
    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=start_at + timedelta(minutes=15)
    )

    lesson = Lesson.objects.create(
        workspace=workspace,
        group=group,
        subject=subject,
        start_at=start_at,
        end_at=end_at
    )

    change_lesson_status(
        workspace=workspace,
        lesson_id=lesson.id,
        action="complete"
    )

    assert not LessonAttendance.objects.filter(
        lesson=lesson,
        student=student
    ).exists()

    lesson.refresh_from_db()

    assert lesson.attendance_initialized_at is not None


def test_teacher_can_mark_student_present(workspace, student, subject):
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

    updated = set_lesson_attendance(
        workspace=workspace,
        lesson_id=lesson.id,
        attendance_id=attendance.id,
        status=LessonAttendance.Status.PRESENT,
        notes="Participated actively.",
        recorded_by=workspace.owner
    )

    assert updated.status == (
        LessonAttendance.Status.PRESENT
    )

    assert updated.recorded_by == workspace.owner

    assert updated.recorded_at is not None

    assert updated.notes == "Participated actively."


def test_teacher_can_correct_attendance(workspace, student, subject):
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

    set_lesson_attendance(
        workspace=workspace,
        lesson_id=lesson.id,
        attendance_id=attendance.id,
        status=LessonAttendance.Status.ABSENT,
        notes="",
        recorded_by=workspace.owner
    )

    set_lesson_attendance(
        workspace=workspace,
        lesson_id=lesson.id,
        attendance_id=attendance.id,
        status=LessonAttendance.Status.PRESENT,
        notes="Attendance corrected.",
        recorded_by=workspace.owner
    )

    attendance.refresh_from_db()

    assert attendance.status == (
        LessonAttendance.Status.PRESENT
    )

    assert attendance.notes == "Attendance corrected."


def test_database_prevents_duplicate_attendance(workspace, student, subject):
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

    with pytest.raises(IntegrityError):

        with transaction.atomic():

            LessonAttendance.objects.create(
                lesson=lesson,
                student=student
            )

    assert LessonAttendance.objects.filter(
        lesson=lesson,
        student=student
    ).count() == 1


def test_completion_rolls_back_if_attendance_fails(workspace, student, subject):
    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    with patch(
        "apps.lessons.services.lifecycle.initialize_lesson_attendance",
        side_effect=RuntimeError(
            "Simulated attendance failure"
        )
    ):

        with pytest.raises(RuntimeError):

            change_lesson_status(
                workspace=workspace,
                lesson_id=lesson.id,
                action="complete"
            )

    lesson.refresh_from_db()

    assert lesson.status == Lesson.Status.SCHEDULED

    assert lesson.attendance_initialized_at is None

    assert LessonAttendance.objects.filter(
        lesson=lesson,
    ).count() == 0