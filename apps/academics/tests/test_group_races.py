from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, close_old_connections

from apps.academics.models import Group, GroupMembership, StudentSubject, Subject

from apps.academics.services import join_student_to_group, update_group

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_join_and_capacity_reduction():

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

    group = Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners",
        max_students=2
    )

    students = []

    for name in ("Anna", "Oleg"):

        student = Student.objects.create(
            workspace=workspace,
            first_name=name,
            last_name="Test"
        )

        StudentSubject.objects.create(
            student=student,
            subject=subject
        )

        students.append(student)

    first_student, second_student = students

    join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=first_student.id
    )

    barrier = Barrier(2)

    def attempt_join():

        close_old_connections()

        try:
            barrier.wait(timeout=10)

            thread_workspace = Workspace.objects.get(id=workspace.id)

            try:
                join_student_to_group(
                    workspace=thread_workspace,
                    group_id=group.id,
                    student_id=second_student.id
                )

            except ValidationError:
                return "rejected"

            return "joined"

        finally:
            connections.close_all()

    def attempt_capacity_reduction():

        close_old_connections()

        try:
            barrier.wait(timeout=10)

            thread_workspace = Workspace.objects.get(id=workspace.id)

            try:
                update_group(
                    workspace=thread_workspace,
                    group_id=group.id,
                    name=group.name,
                    description=group.description,
                    max_students=1
                )

            except ValidationError:
                return "rejected"

            return "capacity_reduced"

        finally:
            connections.close_all()

    with ThreadPoolExecutor(
        max_workers=2,
    ) as executor:

        futures = [
            executor.submit(attempt_join),
            executor.submit(attempt_capacity_reduction)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    group.refresh_from_db()

    active_count = GroupMembership.objects.filter(
        group=group,
        left_at__isnull=True
    ).count()

    assert results.count("rejected") == 1

    assert (
        "joined" in results
        or "capacity_reduced" in results
    )

    assert active_count <= group.max_students