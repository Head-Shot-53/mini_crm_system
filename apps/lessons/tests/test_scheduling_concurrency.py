from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from django.db import IntegrityError, close_old_connections, connection, connections

from django.utils import timezone

from apps.academics.models import Group, StudentSubject, Subject

from apps.lessons.models import Lesson

from apps.lessons.services.creation import create_group_lesson, create_individual_lesson

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_lesson_creation():

    if connection.vendor != "postgresql":
        pytest.skip(
            "This test requires PostgreSQL."
        )

    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Test Workspace"
    )

    subject = Subject.objects.create(
        workspace=workspace,
        name="Python"
    )

    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    StudentSubject.objects.create(
        student=student,
        subject=subject
    )

    group = Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners"
    )

    start_at = (
        timezone.now() + timedelta(days=3)
    ).replace(
        second=0,
        microsecond=0
    )

    end_at = start_at + timedelta(hours=1)

    barrier = Barrier(2)

    def create_individual():
        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(
                id=workspace.id
            )

            barrier.wait(timeout=10)

            try:
                create_individual_lesson(
                    workspace=thread_workspace,
                    student_id=student.id,
                    subject_id=subject.id,
                    start_at=start_at,
                    end_at=end_at
                )

            except (
                ValidationError,
                IntegrityError
            ):
                return "rejected"

            return "created"

        finally:
            connections.close_all()

    def create_group():
        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(
                id=workspace.id
            )

            barrier.wait(timeout=10)

            try:
                create_group_lesson(
                    workspace=thread_workspace,
                    group_id=group.id,
                    start_at=start_at,
                    end_at=end_at
                )

            except (
                ValidationError,
                IntegrityError,
            ):
                return "rejected"

            return "created"

        finally:
            connections.close_all()

    with ThreadPoolExecutor(
        max_workers=2,
    ) as executor:

        futures = [
            executor.submit(create_individual),
            executor.submit(create_group)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    assert sorted(results) == [
        "created",
        "rejected"
    ]

    assert Lesson.objects.filter(
        workspace=workspace
    ).count() == 1