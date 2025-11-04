from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from django.contrib.auth import get_user_model
from django.db import connection, connections, close_old_connections

from django.utils import timezone

from apps.academics.models import Subject
from apps.academics.services import assign_subject_to_student

from apps.homework.models import Assignment, AssignmentRecipient, AssignmentSubmission, AssignmentSubmissionAttempt

from apps.homework.services.publication import publish_assignment
from apps.homework.services.submissions import submit_assignment_work

from apps.students.models import Student
from apps.workspaces.models import Workspace


@pytest.mark.django_db(transaction=True)
def test_concurrent_submissions_create_sequential_revisions():

    if connection.vendor != "postgresql":
        pytest.skip(
            "This test requires PostgreSQL."
        )

    User = get_user_model()


    teacher = User.objects.create_user(
        email="submission-concurrency@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Submission Concurrency Workspace"
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
        title="Python Functions",
        description="Complete exercises 1–10.",
        due_at=timezone.now() + timedelta(days=7)
    )

    publish_assignment(
        workspace=workspace,
        assignment_id=assignment.id
    )

    assignment.refresh_from_db()

    assert assignment.status == Assignment.Status.PUBLISHED

    recipient = AssignmentRecipient.objects.get(
        assignment=assignment,
        student=student
    )

    assert AssignmentSubmission.objects.filter(
        recipient=recipient
    ).count() == 0

    assert AssignmentSubmissionAttempt.objects.count() == 0


    barrier = Barrier(2)

    def attempt_submit(answer_text):
        close_old_connections()

        try:
            thread_workspace = Workspace.objects.get(id=workspace.id)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid()"
                )
                backend_pid = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            submit_assignment_work(
                workspace=thread_workspace,
                recipient_id=recipient.id,
                answer_text=answer_text,
                recorded_by=thread_workspace.owner
            )

            return {
                "result": "submitted",
                "backend_pid": backend_pid
            }

        finally:
            connections.close_all()


    with ThreadPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(
                attempt_submit,
                "Solution from request A"
            ),
            executor.submit(
                attempt_submit,
                "Solution from request B"
            )
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]


    assert sorted(
        result["result"]
        for result in results
    ) == [
        "submitted",
        "submitted"
    ]

    backend_pids = {
        result["backend_pid"]
        for result in results
    }

    assert len(backend_pids) == 2


    assert AssignmentSubmission.objects.filter(
        recipient=recipient
    ).count() == 1

    submission = AssignmentSubmission.objects.get(recipient=recipient)

    attempts = AssignmentSubmissionAttempt.objects.filter(submission=submission)

    assert attempts.count() == 2

    revisions = list(
        AssignmentSubmissionAttempt.objects
        .filter(submission=submission)
        .order_by("revision")
        .values_list(
            "revision",
            flat=True
        )
    )

    assert revisions == [1, 2]

    answer_texts = set(
        attempts.values_list(
            "answer_text",
            flat=True
        )
    )

    assert answer_texts == {
        "Solution from request A",
        "Solution from request B"
    }