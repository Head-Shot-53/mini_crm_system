from datetime import timedelta

import pytest

from django.utils import timezone

from apps.academics.models import GroupMembership
from apps.academics.services import  leave_student_from_group

from apps.lessons.models import Lesson,  LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status


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