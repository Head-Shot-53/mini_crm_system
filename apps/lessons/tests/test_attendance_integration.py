from datetime import timedelta

import pytest

from django.utils import timezone

from django.core.exceptions import ValidationError

from apps.academics.models import GroupMembership
from apps.academics.services import  leave_student_from_group
from apps.academics.services import assign_subject_to_student

from apps.lessons.models import Lesson,  LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status

from apps.students.models import Student

pytestmark = pytest.mark.django_db


def test_attendance_snapshot_survives_group_leave(workspace, student, subject, group, enrollment):
    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    membership = GroupMembership.objects.create(
        group=group,
        student=student,
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

    attendance = LessonAttendance.objects.get(
        lesson=lesson,
        student=student
    )

    leave_student_from_group(
        workspace=workspace,
        group_id=group.id,
        student_id=student.id
    )

    membership.refresh_from_db()
    attendance.refresh_from_db()

    assert membership.left_at is not None

    assert attendance.student == student

    assert attendance.group_membership == membership

    assert LessonAttendance.objects.filter(
        lesson=lesson,
    ).count() == 1


@pytest.mark.django_db
def test_overlapping_membership_history_rolls_back_completion(workspace, student, subject, group):
    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=start_at - timedelta(days=2),
        left_at=start_at + timedelta(minutes=30)
    )

    GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=start_at - timedelta(days=1),
        left_at=start_at + timedelta(minutes=15)
    )

    lesson = Lesson.objects.create(
        workspace=workspace,
        group=group,
        subject=subject,
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

    assert lesson.status == Lesson.Status.SCHEDULED

    assert lesson.completed_at is None

    assert lesson.attendance_initialized_at is None

    assert not LessonAttendance.objects.filter(
        lesson=lesson,
    ).exists()


@pytest.mark.django_db
def test_attendance_snapshot_survives_new_student_join(workspace, student, subject, group, enrollment):

    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    membership = GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=start_at - timedelta(days=1)
    )


    GroupMembership.objects.filter(
        pk=membership.pk
    ).update(
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

    lesson.refresh_from_db()

    assert lesson.status == Lesson.Status.COMPLETED


    assert LessonAttendance.objects.filter(
        lesson=lesson
    ).count() == 1

    original_attendance = LessonAttendance.objects.get(
        lesson=lesson,
        student=student
    )

    assert original_attendance.group_membership_id == membership.id

    new_student = Student.objects.create(
        workspace=workspace,
        first_name="Maria",
        last_name="Nowak"
    )


    new_enrollment = assign_subject_to_student(
        workspace=workspace,
        student_id=new_student.id,
        subject_id=subject.id,
        level="Beginner"
    )

    assert new_enrollment is not None


    new_membership = GroupMembership.objects.create(
        group=group,
        student=new_student,
        joined_at=timezone.now()
    )

    new_membership.refresh_from_db()

    assert new_membership.joined_at > lesson.end_at


    lesson.refresh_from_db()
    original_attendance.refresh_from_db()


    assert lesson.status == Lesson.Status.COMPLETED

    assert LessonAttendance.objects.filter(
        lesson=lesson
    ).count() == 1

    assert LessonAttendance.objects.filter(
        lesson=lesson,
        student=student
    ).exists()

    assert not LessonAttendance.objects.filter(
        lesson=lesson,
        student=new_student
    ).exists()

    assert original_attendance.group_membership_id == membership.id


@pytest.mark.django_db
def test_attendance_includes_student_who_left_during_lesson(workspace, student, subject, group, enrollment):

    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    joined_at = start_at - timedelta(days=1)

    left_at = start_at + timedelta(minutes=30)


    membership = GroupMembership.objects.create(
        group=group,
        student=student,
        joined_at=joined_at
    )


    GroupMembership.objects.filter(
        pk=membership.pk
    ).update(
        joined_at=joined_at,
        left_at=left_at
    )

    membership.refresh_from_db()


    assert membership.joined_at < start_at

    assert membership.left_at is not None

    assert start_at < membership.left_at < end_at


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


    lesson.refresh_from_db()
    membership.refresh_from_db()


    assert lesson.status == Lesson.Status.COMPLETED

    assert lesson.attendance_initialized_at is not None

    attendance = LessonAttendance.objects.get(
        lesson=lesson,
        student=student
    )

    assert attendance.student_id == student.id

    assert attendance.group_membership_id == membership.id

    assert membership.left_at == left_at

    assert LessonAttendance.objects.filter(
        lesson=lesson
    ).count() == 1