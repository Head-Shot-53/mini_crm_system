from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import Group, StudentSubject, Subject
from apps.students.models import Student

from apps.lessons.models import Lesson


def validate_lesson_time(*, start_at, end_at):
    if not isinstance(start_at, datetime):
        raise ValidationError(
            "Lesson start must be a datetime."
        )

    if not isinstance(end_at, datetime):
        raise ValidationError(
            "Lesson end must be a datetime."
        )

    if timezone.is_naive(start_at):
        raise ValidationError(
            "Lesson start must be timezone-aware."
        )

    if timezone.is_naive(end_at):
        raise ValidationError(
            "Lesson end must be timezone-aware."
        )

    if end_at <= start_at:
        raise ValidationError(
            "Lesson end must be later than start."
        )

    if start_at <= timezone.now():
        raise ValidationError(
            "New lessons must be scheduled in the future."
        )


@transaction.atomic
def create_individual_lesson(*, workspace, student_id, subject_id, start_at, end_at, notes=""):
    validate_lesson_time(
        start_at=start_at,
        end_at=end_at
    )

    student = (
        Student.objects
        .select_for_update()
        .get(
            id=student_id,
            workspace=workspace
        )
    )

    if student.status != Student.Status.ACTIVE:
        raise ValidationError(
            "Only active students can have "
            "new individual lessons scheduled."
        )

    subject = (
        Subject.objects
        .select_for_update()
        .get(
            id=subject_id,
            workspace=workspace
        )
    )

    if not subject.is_active:
        raise ValidationError(
            "Cannot schedule a lesson "
            "for an inactive subject."
        )

    has_active_enrollment = (
        StudentSubject.objects
        .filter(
            student=student,
            subject=subject,
            status=StudentSubject.Status.ACTIVE
        )
        .exists()
    )

    if not has_active_enrollment:
        raise ValidationError(
            "Student must have an active "
            "enrollment in this subject."
        )

    lesson = Lesson(
        workspace=workspace,
        student=student,
        subject=subject,
        start_at=start_at,
        end_at=end_at,
        notes=notes.strip()
    )

    lesson.full_clean()

    lesson.save()

    return lesson


@transaction.atomic
def create_group_lesson(*, workspace, group_id, start_at, end_at, notes=""):
    validate_lesson_time(
        start_at=start_at,
        end_at=end_at
    )

    group = (
        Group.objects
        .select_for_update()
        .get(
            id=group_id,
            workspace=workspace
        )
    )

    if not group.is_active:
        raise ValidationError(
            "Cannot schedule lessons "
            "for an inactive group."
        )

    subject = (
        Subject.objects
        .select_for_update()
        .get(
            id=group.subject_id,
            workspace=workspace
        )
    )

    if not subject.is_active:
        raise ValidationError(
            "Cannot schedule a lesson "
            "for an inactive subject."
        )

    lesson = Lesson(
        workspace=workspace,
        group=group,
        subject=subject,
        start_at=start_at,
        end_at=end_at,
        notes=notes.strip()
    )

    lesson.full_clean()

    lesson.save()

    return lesson