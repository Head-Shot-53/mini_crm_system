from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.students.models import Student

STATUS_TRANSITIONS = {
    "pause": {
        Student.Status.ACTIVE: Student.Status.PAUSED,
    },

    "resume": {
        Student.Status.PAUSED: Student.Status.ACTIVE,
    },

    "complete": {
        Student.Status.ACTIVE: Student.Status.COMPLETED,
        Student.Status.PAUSED: Student.Status.COMPLETED,
    },

    "reopen": {
        Student.Status.COMPLETED: Student.Status.ACTIVE,
    },

    "archive": {
        Student.Status.ACTIVE: Student.Status.ARCHIVED,
        Student.Status.PAUSED: Student.Status.ARCHIVED,
        Student.Status.COMPLETED: Student.Status.ARCHIVED,
    },
}

@transaction.atomic
def change_student_status(*,workspace,student_id,action):
    if action not in STATUS_TRANSITIONS and action != "restore":
        raise ValidationError(
            "Unsupported student status action."
        )

    student = (Student.objects.select_for_update().get(id=student_id,workspace=workspace))

    if action == "restore":
        if student.status != Student.Status.ARCHIVED:
            raise ValidationError(
                "Only archived students can be restored."
            )

        allowed_previous_statuses = {
            Student.Status.ACTIVE,
            Student.Status.PAUSED,
            Student.Status.COMPLETED,
        }

        previous_status = student.status_before_archive

        if previous_status not in allowed_previous_statuses:
            previous_status = Student.Status.ACTIVE

        student.status = previous_status
        student.status_before_archive = ""
        student.archived_at = None

    else:
        transitions = STATUS_TRANSITIONS[action]

        new_status = transitions.get(student.status)

        if new_status is None:
            raise ValidationError(
                f"Action '{action}' is not allowed "
                f"for student status '{student.status}'."
            )

        if action == "archive":
            student.status_before_archive = student.status
            student.archived_at = timezone.now()

        student.status = new_status

    student.save(
        update_fields=[
            "status",
            "status_before_archive",
            "archived_at",
            "updated_at",
        ]
    )

    return student