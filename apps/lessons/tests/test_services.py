from datetime import timedelta

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model


from apps.workspaces.models import Workspace
from apps.academics.models import StudentSubject
from apps.lessons.models import Lesson
from apps.lessons.services.creation import create_group_lesson, create_individual_lesson

from apps.students.models import Student


pytestmark = pytest.mark.django_db


def test_create_individual_lesson(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    assert lesson.workspace == workspace
    assert lesson.student == student
    assert lesson.subject == subject
    assert lesson.group is None

    assert Lesson.objects.filter(
        id=lesson.id
    ).exists()


def test_create_group_lesson(workspace, group, subject, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_group_lesson(
        workspace=workspace,
        group_id=group.id,
        start_at=start_at,
        end_at=end_at
    )

    assert lesson.workspace == workspace
    assert lesson.group == group
    assert lesson.subject == subject
    assert lesson.student is None


def test_cannot_schedule_without_active_enrollment(workspace, student, subject, enrollment, lesson_time):
    enrollment.status = StudentSubject.Status.PAUSED

    enrollment.save(update_fields=["status"])

    start_at, end_at = lesson_time

    with pytest.raises(ValidationError):
        create_individual_lesson(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
            start_at=start_at,
            end_at=end_at
        )

    assert Lesson.objects.count() == 0


def test_cannot_schedule_for_archived_student(workspace, student, subject, enrollment, lesson_time):
    student.status = Student.Status.ARCHIVED

    student.save(update_fields=["status"])

    start_at, end_at = lesson_time

    with pytest.raises(ValidationError):
        create_individual_lesson(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
            start_at=start_at,
            end_at=end_at
        )

    assert Lesson.objects.count() == 0


def test_cannot_schedule_invalid_time(workspace, student, subject, enrollment, lesson_time):
    start_at, _ = lesson_time

    with pytest.raises(ValidationError):
        create_individual_lesson(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
            start_at=start_at,
            end_at=start_at
        )


def test_cannot_schedule_past_lesson(workspace, student, subject, enrollment):
    start_at = timezone.now() - timedelta(days=1)

    end_at = start_at + timedelta(hours=1)

    with pytest.raises(ValidationError):
        create_individual_lesson(
            workspace=workspace,
            student_id=student.id,
            subject_id=subject.id,
            start_at=start_at,
            end_at=end_at
        )


def test_cannot_schedule_foreign_student(workspace, subject, lesson_time):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_student = Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    start_at, end_at = lesson_time

    with pytest.raises(Student.DoesNotExist):
        create_individual_lesson(
            workspace=workspace,
            student_id=foreign_student.id,
            subject_id=subject.id,
            start_at=start_at,
            end_at=end_at
        )

    assert Lesson.objects.count() == 0