from django.db.models import Q

from .models import Student


def get_filtered_students(*, workspace, archived=False, q="", status=None, subject=None):
    students = Student.objects.filter(workspace=workspace)

    if archived:
        students = students.filter(status=Student.Status.ARCHIVED)

    else:
        students = students.exclude(status=Student.Status.ARCHIVED)

        if status:
            students = students.filter(status=status)

    if q:
        for term in q.split():
            students = students.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
                | Q(phone__icontains=term)
            )

    if subject is not None:
        students = students.filter(
            subject_enrollments__subject=subject,
            subject_enrollments__subject__workspace=workspace
        )

    return students.order_by("last_name", "first_name", "id")