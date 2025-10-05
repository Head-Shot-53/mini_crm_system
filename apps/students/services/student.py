from django.core.exceptions import ValidationError
from django.db import transaction

from apps.students.models import Student


EDITABLE_STUDENT_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "start_date",
    "default_lesson_price"
)


@transaction.atomic
def update_student_details(*, workspace, student_id, data):
    student = (
        Student.objects
        .select_for_update()
        .get(
            id=student_id,
            workspace=workspace
        )
    )

    if student.status == Student.Status.ARCHIVED:
        raise ValidationError(
            "Archived students cannot be edited."
        )

    for field in EDITABLE_STUDENT_FIELDS:
        if field in data:
            setattr(
                student,
                field,
                data[field]
            )

    student.full_clean()

    student.save(
        update_fields=[
            *EDITABLE_STUDENT_FIELDS,
            "updated_at"
        ]
    )

    return student