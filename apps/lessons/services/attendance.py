from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import Group, GroupMembership

from apps.lessons.models import Lesson, LessonAttendance

from apps.lessons.selectors import get_workspace_lessons

from apps.students.models import Student

from .availability import lock_workspace_for_scheduling


def initialize_lesson_attendance(*, workspace, lesson, timestamp):
    """
    Called inside the transaction that completes a lesson.

    The caller must already hold:
    1. Workspace lock.
    2. Lesson lock.
    """

    if lesson.workspace_id != workspace.id:
        raise ValidationError(
            "Lesson belongs to another workspace."
        )

    if lesson.status != Lesson.Status.COMPLETED:
        raise ValidationError(
            "Attendance can only be initialized "
            "for completed lessons."
        )

    if lesson.attendance_initialized_at is not None:
        raise ValidationError(
            "Attendance has already been initialized."
        )

    records = []

    if lesson.student_id is not None:

        student = Student.objects.get(
            id=lesson.student_id,
            workspace=workspace
        )

        records.append(
            LessonAttendance(
                lesson=lesson,
                student=student
            )
        )

    else:

        group = (
            Group.objects
            .select_for_update(of=("self",))
            .get(
                id=lesson.group_id,
                workspace=workspace,
                subject_id=lesson.subject_id,
                subject__workspace=workspace
            )
        )

        memberships = (
            GroupMembership.objects
            .filter(
                group=group,
                joined_at__lte=lesson.start_at
            )
            .filter(
                Q(left_at__isnull=True)
                | Q(left_at__gt=lesson.start_at)
            )
            .select_related("student")
            .order_by(
                "student_id",
                "joined_at",
                "id"
            )
        )

        seen_students = set()

        for membership in memberships:

            if membership.student.workspace_id != workspace.id:
                raise ValidationError(
                    "Invalid cross-workspace group membership."
                )

            if membership.student_id in seen_students:
                continue

            seen_students.add(membership.student_id)

            records.append(
                LessonAttendance(
                    lesson=lesson,
                    student=membership.student,
                    group_membership=membership
                )
            )

    for record in records:
        record.full_clean()

    LessonAttendance.objects.bulk_create(records)

    lesson.attendance_initialized_at = timestamp

    lesson.save(
        update_fields=[
            "attendance_initialized_at",
            "updated_at"
        ]
    )

    return records


@transaction.atomic
def set_lesson_attendance(*, workspace, lesson_id, attendance_id, status, notes, recorded_by):
    allowed_statuses = {
        LessonAttendance.Status.PRESENT,
        LessonAttendance.Status.ABSENT,
        LessonAttendance.Status.LATE,
        LessonAttendance.Status.EXCUSED
    }

    if status not in allowed_statuses:
        raise ValidationError(
            "Invalid attendance status."
        )

    if recorded_by.pk != workspace.owner_id:
        raise ValidationError(
            "Only the workspace owner "
            "can record attendance in V1."
        )

    if not recorded_by.is_active:
        raise ValidationError(
            "Inactive users cannot record attendance."
        )

    if len(notes) > 1000:
        raise ValidationError(
            "Attendance notes cannot exceed "
            "1000 characters."
        )

    lock_workspace_for_scheduling(workspace=workspace)

    lesson = (
        Lesson.objects
        .select_for_update(of=("self",))
        .get(
            id=lesson_id,
            workspace=workspace
        )
    )

    is_accessible = (
        get_workspace_lessons(workspace=workspace)
        .filter(id=lesson.id)
        .exists()
    )

    if not is_accessible:
        raise Lesson.DoesNotExist("Lesson not found.")

    if lesson.status != Lesson.Status.COMPLETED:
        raise ValidationError(
            "Attendance can only be recorded "
            "after completing the lesson."
        )

    if lesson.attendance_initialized_at is None:
        raise ValidationError(
            "Attendance has not been initialized."
        )

    attendance = (
        LessonAttendance.objects
        .select_for_update(of=("self",))
        .get(
            id=attendance_id,
            lesson=lesson,
            student__workspace=workspace
        )
    )

    attendance.status = status
    attendance.notes = notes.strip()
    attendance.recorded_at = timezone.now()
    attendance.recorded_by = recorded_by

    attendance.full_clean()

    attendance.save(
        update_fields=[
            "status",
            "notes",
            "recorded_at",
            "recorded_by",
            "updated_at"
        ]
    )

    return attendance