import pytest

from datetime import timedelta, datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.academics.models import Group, Subject
from apps.homework.models import Assignment
from apps.students.models import Student
from apps.workspaces.models import Workspace
from apps.lessons.models import Lesson


pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(
        owner=teacher,
        name="Test Workspace"
    )


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(
        workspace=workspace,
        name="Python"
    )


@pytest.fixture
def student(workspace):
    return Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )


@pytest.fixture
def group(workspace, subject):
    return Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners"
    )


@pytest.fixture
def deadline():
    return timezone.now() + timedelta(days=7)


def test_create_individual_assignment(workspace, subject, student, deadline):
    assignment = Assignment(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Variables",
        description="Complete exercises 1–5.",
        due_at=deadline
    )

    assignment.full_clean()
    assignment.save()

    assert assignment.id is not None

    assert assignment.assignment_type == "individual"

    assert assignment.group is None

    assert assignment.status == Assignment.Status.DRAFT


def test_create_group_assignment(workspace, subject, group, deadline):
    assignment = Assignment(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Python Functions",
        due_at=deadline
    )

    assignment.full_clean()
    assignment.save()

    assert assignment.assignment_type == "group"

    assert assignment.student is None

    assert assignment.group == group


def test_database_rejects_assignment_without_target(workspace, subject):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(
                workspace=workspace,
                subject=subject,
                title="Invalid Assignment",
            )


def test_database_rejects_two_targets(workspace, subject, student, group):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(
                workspace=workspace,
                subject=subject,
                student=student,
                group=group,
                title="Invalid Assignment"
            )


def test_database_rejects_publication_without_timestamp(workspace, subject, student, deadline):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(
                workspace=workspace,
                subject=subject,
                student=student,
                title="Invalid Publication",
                status=Assignment.Status.PUBLISHED,
                due_at=deadline,
                published_at=None
            )


def test_cannot_assign_foreign_subject(workspace, student):
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

    assignment = Assignment(
        workspace=workspace,
        subject=foreign_subject,
        student=student,
        title="Foreign Subject Assignment"
    )

    with pytest.raises(ValidationError):
        assignment.full_clean()


def test_assignment_rejects_naive_deadline(workspace, subject, student):
    assignment = Assignment(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Practice",
        due_at=datetime(2027, 1, 10, 18, 0)
    )

    with pytest.raises(ValidationError):
        assignment.full_clean()


def test_assignment_lesson_must_match_student(workspace, subject, student, deadline):
    another_student = Student.objects.create(
        workspace=workspace,
        first_name="Oleg",
        last_name="Ivanov"
    )

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        student=another_student,
        start_at=timezone.now() + timedelta(days=2),
        end_at=timezone.now() + timedelta(days=2, hours=1)
    )

    assignment = Assignment(
        workspace=workspace,
        subject=subject,
        student=student,
        lesson=lesson,
        title="Python Functions",
        due_at=deadline
    )

    with pytest.raises(ValidationError):
        assignment.full_clean()