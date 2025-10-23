import pytest

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.lessons.models import Lesson, LessonAttendance

from apps.students.models import Student
from apps.workspaces.models import Workspace
from apps.academics.models import Subject, Group, GroupMembership



pytestmark = pytest.mark.django_db


def test_lesson_audit_detects_foreign_student(workspace, subject):

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

    start_at = timezone.now() + timedelta(days=2)

    # Intentionally bypass model validation.
    Lesson.objects.create(
        workspace=workspace,
        student=foreign_student,
        subject=subject,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1)
    )

    with pytest.raises(CommandError):
        call_command(
            "audit_lesson_integrity"
        )


def test_lesson_audit_detects_foreign_subject(workspace):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    start_at = timezone.now() + timedelta(days=2)

    Lesson.objects.create(
        workspace=workspace,
        student=student,
        subject=foreign_subject,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1)
    )

    with pytest.raises(CommandError):
        call_command("audit_lesson_integrity")


def test_lesson_audit_detects_foreign_group(workspace, subject):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    foreign_group = Group.objects.create(
        workspace=foreign_workspace,
        subject=foreign_subject,
        name="Foreign Group",
        max_students=5
    )

    start_at = timezone.now() + timedelta(days=2)

    Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        group=foreign_group,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1)
    )

    with pytest.raises(CommandError):
        call_command("audit_lesson_integrity")


def test_lesson_audit_detects_invalid_attendance_membership(workspace, subject):
    group_a = Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Group A",
        max_students=5
    )

    group_b = Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Group B",
        max_students=5
    )

    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    wrong_membership = GroupMembership.objects.create(
        group=group_b,
        student=student
    )

    start_at = timezone.now() + timedelta(days=2)

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        group=group_a,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1)
    )

    LessonAttendance.objects.create(
        lesson=lesson,
        student=student,
        group_membership=wrong_membership
    )

    with pytest.raises(CommandError):
        call_command("audit_lesson_integrity")