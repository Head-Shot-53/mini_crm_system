from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.db import connection, connections, close_old_connections
from django.utils import timezone
from django.core.exceptions import ValidationError


from apps.academics.models import Group, GroupMembership, Subject
from apps.academics.services import assign_subject_to_student, join_student_to_group

from apps.homework.models import  Assignment, AssignmentRecipient
from apps.homework.services.publication import publish_assignment

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_publish_same_assignment_creates_one_snapshot():

    if connection.vendor != "postgresql":
        pytest.skip(
            "This test requires PostgreSQL."
        )

    User = get_user_model()


    teacher = User.objects.create_user(
        email="publish-concurrency@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Publication Concurrency Workspace"
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

    assign_subject_to_student(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        level="Beginner"
    )


    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        student=student,
        title="Python Variables",
        description="Complete exercises 1-5.",
        due_at=timezone.now() + timedelta(days=7)
    )

    assert assignment.status == Assignment.Status.DRAFT
    assert assignment.published_at is None


    barrier = Barrier(2)

    def attempt_publish():

        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(id=workspace.id)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )

                backend_pid = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            try:
                publish_assignment(
                    workspace=thread_workspace,
                    assignment_id=assignment.id
                )

            except ValidationError:
                return {
                    "result": "rejected",
                    "backend_pid": backend_pid
                }

            return {
                "result": "published",
                "backend_pid": backend_pid
            }

        finally:
            connections.close_all()


    with ThreadPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(attempt_publish)
            for _ in range(2)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    backend_pids = {
        result["backend_pid"]
        for result in results
    }

    assert len(backend_pids) == 2

    outcomes = sorted(
        result["result"]
        for result in results
    )

    assert outcomes == [
        "published",
        "rejected"
    ]


    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.PUBLISHED
    assert assignment.published_at is not None

    recipients = AssignmentRecipient.objects.filter(
        assignment=assignment,
    )

    assert recipients.count() == 1

    recipient = recipients.get()

    assert recipient.student_id == student.id


@pytest.mark.django_db(transaction=True)
def test_concurrent_group_assignment_publish_and_student_join_preserves_snapshot():

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
        name="Python Group",
        max_students=10
    )


    existing_student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska"
    )

    assign_subject_to_student(
        workspace=workspace,
        student_id=existing_student.id,
        subject_id=subject.id,
        level="Beginner"
    )

    existing_membership = join_student_to_group(
        workspace=workspace,
        group_id=group.id,
        student_id=existing_student.id
    )


    new_student = Student.objects.create(
        workspace=workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    assign_subject_to_student(
        workspace=workspace,
        student_id=new_student.id,
        subject_id=subject.id,
        level="Beginner"
    )

    assert not GroupMembership.objects.filter(
        group=group,
        student=new_student,
        left_at__isnull=True
    ).exists()

    assignment = Assignment.objects.create(
        workspace=workspace,
        subject=subject,
        group=group,
        title="Python Group Homework",
        description="Concurrency snapshot test.",
        due_at=timezone.now() + timedelta(days=7)
    )

    assert assignment.status == Assignment.Status.DRAFT
    assert assignment.published_at is None

    barrier = Barrier(2)

    def publish():
        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(id=workspace.id)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )

                backend_pid = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            publish_assignment(
                workspace=thread_workspace,
                assignment_id=assignment.id
            )

            return backend_pid

        finally:
            connections.close_all()

    def join_maria():
        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(id=workspace.id)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )

                backend_pid = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            join_student_to_group(
                workspace=thread_workspace,
                group_id=group.id,
                student_id=new_student.id
            )

            return backend_pid

        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:

        publish_future = executor.submit(publish)

        join_future = executor.submit(join_maria)

        publish_backend_pid = publish_future.result(timeout=20)

        join_backend_pid = join_future.result(timeout=20)

    assert publish_backend_pid != join_backend_pid

    assignment.refresh_from_db()

    membership = GroupMembership.objects.get(
        group=group,
        student=new_student,
        left_at__isnull=True
    )

    assert assignment.status == Assignment.Status.PUBLISHED
    assert assignment.published_at is not None

    assert membership.joined_at is not None

    assert AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=existing_student
    ).exists()


    is_recipient = AssignmentRecipient.objects.filter(
        assignment=assignment,
        student=new_student
    ).exists()

    was_member_at_publication = (
        membership.joined_at <= assignment.published_at and (
            membership.left_at is None
            or membership.left_at
            > assignment.published_at
        )
    )

    assert is_recipient == was_member_at_publication

    if is_recipient:
        recipient = AssignmentRecipient.objects.get(
            assignment=assignment,
            student=new_student
        )

        assert recipient.group_membership_id == membership.id

        assert AssignmentRecipient.objects.filter(
            assignment=assignment
        ).count() == 2

    else:
        assert not AssignmentRecipient.objects.filter(
            assignment=assignment,
            student=new_student
        ).exists()

        assert AssignmentRecipient.objects.filter(assignment=assignment).count() == 1