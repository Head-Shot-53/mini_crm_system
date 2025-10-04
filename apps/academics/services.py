from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.students.models import Student

from .models import StudentSubject, Subject


@transaction.atomic
def assign_subject_to_student(*,workspace,student_id,subject_id,level="",started_on=None,):
    student = (Student.objects.select_for_update().get(
            id=student_id,
            workspace=workspace,
        )
    )

    subject = Subject.objects.get(id=subject_id,workspace=workspace,is_active=True)

    if student.status == Student.Status.ARCHIVED:
        raise ValidationError(
            "Cannot assign subjects to an archived student."
        )

    enrollment = StudentSubject(
        student=student,
        subject=subject,
        level=level,
        started_on=started_on or timezone.localdate(),
    )

    enrollment.full_clean()

    enrollment.save()

    return enrollment


ENROLLMENT_STATUS_TRANSITIONS = {
    StudentSubject.Status.ACTIVE: {
        StudentSubject.Status.PAUSED,
        StudentSubject.Status.COMPLETED,
    },

    StudentSubject.Status.PAUSED: {
        StudentSubject.Status.ACTIVE,
        StudentSubject.Status.COMPLETED,
    },

    StudentSubject.Status.COMPLETED: {
        StudentSubject.Status.ACTIVE,
    },
}


@transaction.atomic
def update_student_enrollment(*, workspace, student_id, enrollment_id, level, status, started_on, notes):
    student = Student.objects.select_for_update().get(id=student_id,workspace=workspace)

    if student.status == Student.Status.ARCHIVED:
        raise ValidationError(
            "Cannot edit enrollments of an archived student."
        )

    enrollment = (
        StudentSubject.objects
        .select_related("subject")
        .select_for_update(of=("self",))
        .get(
            id=enrollment_id,
            student=student,
            subject__workspace=workspace,
        )
    )

    current_status = enrollment.status

    if status != current_status:
        allowed_statuses = (
            ENROLLMENT_STATUS_TRANSITIONS.get(current_status,set())
        )

        if status not in allowed_statuses:
            raise ValidationError(
                "This enrollment status transition is not allowed."
            )

    enrollment.level = level.strip()
    enrollment.status = status
    enrollment.started_on = started_on
    enrollment.notes = notes.strip()

    enrollment.full_clean()

    enrollment.save(
        update_fields=[
            "level",
            "status",
            "started_on",
            "notes",
            "updated_at",
        ]
    )

    return enrollment