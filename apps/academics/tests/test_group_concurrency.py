from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, close_old_connections

from apps.academics.models import Group, Subject, StudentSubject, GroupMembership

from apps.academics.services import join_student_to_group

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_join_cannot_exceed_capacity():
    if connection.vendor != "postgresql":
        pytest.skip(
            "Concurrency test requires PostgreSQL."
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
        max_students=1
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

    barrier = Barrier(2)

    def attempt_join(student_id):
        close_old_connections()

        try:
            barrier.wait(timeout=10)

            thread_workspace = Workspace.objects.get(
                id=workspace.id
            )

            try:
                join_student_to_group(
                    workspace=thread_workspace,
                    group_id=group.id,
                    student_id=student_id
                )

            except ValidationError:
                return "rejected"

            return "joined"

        finally:
            connections.close_all()

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                attempt_join,
                student.id
            )
            for student in students
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    assert sorted(results) == ["joined", "rejected"]

    assert GroupMembership.objects.filter(
        group=group,
        left_at__isnull=True
    ).count() == 1