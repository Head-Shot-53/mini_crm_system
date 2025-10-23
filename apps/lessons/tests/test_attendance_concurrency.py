from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from django.db import connection, connections, close_old_connections

from django.utils import timezone

from apps.academics.models import Subject, Group, GroupMembership
from apps.academics.services import leave_student_from_group

from apps.lessons.models import Lesson, LessonAttendance
from apps.lessons.services.lifecycle import change_lesson_status

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_completion_creates_one_attendance():

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

    now = timezone.now()

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1)
    )

    barrier = Barrier(2)

    def attempt_completion():

        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(id=workspace.id)

            barrier.wait(timeout=10)

            try:
                change_lesson_status(
                    workspace=thread_workspace,
                    lesson_id=lesson.id,
                    action="complete"
                )

            except ValidationError:
                return "rejected"

            return "completed"

        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(attempt_completion)
            for _ in range(2)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    lesson.refresh_from_db()

    assert sorted(results) == [
        "completed",
        "rejected"
    ]

    assert lesson.status == Lesson.Status.COMPLETED

    assert lesson.attendance_initialized_at is not None

    assert LessonAttendance.objects.filter(
        lesson=lesson,
        student=student,
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_completion_and_group_leave_preserves_attendance():

    if connection.vendor != "postgresql":
        pytest.skip(
            "This test requires PostgreSQL."
        )

    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher_leave@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Concurrency Workspace"
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

    group = Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Group",
        max_students=5
    )

    now = timezone.now()

    start_at = now - timedelta(hours=2)
    end_at = now - timedelta(hours=1)

    lesson = Lesson.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        status=Lesson.Status.SCHEDULED,
        start_at=start_at,
        end_at=end_at
    )

    membership = GroupMembership.objects.create(
        group=group,
        student=student
    )

    GroupMembership.objects.filter(
        pk=membership.pk,
    ).update(
        joined_at=start_at - timedelta(days=1),
        left_at=None
    )

    membership.refresh_from_db()

    assert membership.joined_at < lesson.start_at
    assert membership.left_at is None

    barrier = Barrier(2)

    def complete_lesson():

        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(
                id=workspace.id,
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )
                connection_id = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            change_lesson_status(
                workspace=thread_workspace,
                lesson_id=lesson.id,
                action="complete"
            )

            return connection_id

        finally:
            connections.close_all()

    def leave_group():

        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(
                id=workspace.id,
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )
                connection_id = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            leave_student_from_group(
                workspace=thread_workspace,
                group_id=group.id,
                student_id=student.id,
            )

            return connection_id

        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:

        completion_future = executor.submit(complete_lesson)

        leave_future = executor.submit(leave_group)

        completion_connection = completion_future.result(timeout=20)

        leave_connection = leave_future.result(timeout=20)

    assert completion_connection != leave_connection

    lesson.refresh_from_db()
    membership.refresh_from_db()

    assert lesson.status == Lesson.Status.COMPLETED

    assert membership.left_at is not None

    assert lesson.attendance_initialized_at is not None

    attendance = LessonAttendance.objects.get(
        lesson=lesson,
        student=student,
    )

    assert attendance.group_membership_id == membership.id