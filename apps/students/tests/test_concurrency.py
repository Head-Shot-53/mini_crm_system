from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, close_old_connections

from apps.academics.models import StudentSubject
from apps.academics.services import assign_subject_to_student

from apps.students.models import Student
from apps.students.services.lifecycle import change_student_status
from apps.students.services.student import update_student_details


@pytest.mark.django_db(transaction=True)
def test_concurrent_subject_assignment(workspace, student, subject):
    if connection.vendor != "postgresql":
        pytest.skip(
            "Concurrency test requires PostgreSQL."
        )

    barrier = Barrier(2)

    def assign():
        close_old_connections()

        try:
            barrier.wait(timeout=10)

            try:
                assign_subject_to_student(
                    workspace=workspace,
                    student_id=student.id,
                    subject_id=subject.id,
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
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(assign)
            for _ in range(2)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    assert sorted(results) == [
        "created",
        "rejected"
    ]

    assert StudentSubject.objects.filter(
        student=student,
        subject=subject
    ).count() == 1


@pytest.mark.django_db
def test_cannot_update_student_after_archiving(workspace, student):
    change_student_status(
        workspace=workspace,
        student_id=student.id,
        action="archive"
    )

    with pytest.raises(ValidationError):
        update_student_details(
            workspace=workspace,
            student_id=student.id,
            data={
                "first_name": "Changed",
                "last_name": "Name",
                "start_date": date(2026, 9, 1)
            }
        )

    student.refresh_from_db()

    assert student.status == Student.Status.ARCHIVED

    assert student.first_name == "Anna"

    assert student.last_name == "Kowalska"