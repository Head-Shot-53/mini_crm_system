from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics.models import Group, Subject
from apps.homework.models import Assignment
from apps.lessons.models import Lesson
from apps.students.models import Student


def _get_subject(*, workspace, subject_id):
    return Subject.objects.get(
        id=subject_id,
        workspace=workspace,
    )


def _get_student(*, workspace, student_id):
    if student_id is None:
        return None

    return Student.objects.get(
        id=student_id,
        workspace=workspace
    )


def _get_group(*, workspace, group_id):
    if group_id is None:
        return None

    return Group.objects.get(
        id=group_id,
        workspace=workspace
    )


def _get_lesson(*, workspace, lesson_id):
    if lesson_id is None:
        return None

    return Lesson.objects.get(
        id=lesson_id,
        workspace=workspace
    )


@transaction.atomic
def create_assignment_draft(*, workspace, subject_id, title, description="", due_at=None, student_id=None, group_id=None, lesson_id=None):
    subject = _get_subject(
        workspace=workspace,
        subject_id=subject_id
    )

    student = _get_student(
        workspace=workspace,
        student_id=student_id
    )

    group = _get_group(
        workspace=workspace,
        group_id=group_id
    )

    lesson = _get_lesson(
        workspace=workspace,
        lesson_id=lesson_id
    )

    assignment = Assignment(
        workspace=workspace,
        subject=subject,
        student=student,
        group=group,
        lesson=lesson,
        title=title,
        description=description,
        due_at=due_at,
        status=Assignment.Status.DRAFT
    )

    assignment.full_clean()
    assignment.save()

    return assignment


@transaction.atomic
def update_assignment_draft(*, workspace, assignment_id, subject_id, title, description="", due_at=None, student_id=None, group_id=None, lesson_id=None):

    assignment = (
        Assignment.objects
        .select_for_update()
        .get(
            id=assignment_id,
            workspace=workspace
        )
    )

    if assignment.status != Assignment.Status.DRAFT:
        raise ValidationError(
            "Only draft assignments can be edited."
        )

    subject = _get_subject(
        workspace=workspace,
        subject_id=subject_id
    )

    student = _get_student(
        workspace=workspace,
        student_id=student_id
    )

    group = _get_group(
        workspace=workspace,
        group_id=group_id
    )

    lesson = _get_lesson(
        workspace=workspace,
        lesson_id=lesson_id
    )

    assignment.subject = subject
    assignment.student = student
    assignment.group = group
    assignment.lesson = lesson
    assignment.title = title
    assignment.description = description
    assignment.due_at = due_at

    assignment.full_clean()
    assignment.save()

    return assignment