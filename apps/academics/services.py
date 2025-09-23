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