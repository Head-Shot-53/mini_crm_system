from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.students.models import Student

from .models import StudentSubject, Subject, Group, GroupMembership


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


@transaction.atomic
def create_group(*, workspace, subject_id, name, description="", max_students=None):
    subject = Subject.objects.get(
        id=subject_id,
        workspace=workspace,
        is_active=True
    )

    group = Group(
        workspace=workspace,
        subject=subject,
        name=name.strip(),
        description=description.strip(),
        max_students=max_students
    )

    group.full_clean()

    group.save()

    return group


@transaction.atomic
def join_student_to_group(*, workspace, group_id, student_id):
    student = Student.objects.select_for_update().get(id=student_id,workspace=workspace)

    group = Group.objects.select_for_update().get(id=group_id, workspace=workspace)

    if student.status != Student.Status.ACTIVE:
        raise ValidationError(
            "Only active students can join groups."
        )

    if not group.is_active:
        raise ValidationError(
            "Cannot join an inactive group."
        )

    if not group.subject.is_active:
        raise ValidationError(
            "The group's subject is inactive."
        )

    has_active_enrollment = (
        StudentSubject.objects
        .filter(
            student=student,
            subject_id=group.subject_id,
            subject__workspace=workspace,
            status=StudentSubject.Status.ACTIVE
        )
        .exists()
    )

    if not has_active_enrollment:
        raise ValidationError(
            "Student must have an active enrollment "
            "in the group's subject."
        )

    active_memberships = GroupMembership.objects.filter(group=group, left_at__isnull=True)

    if active_memberships.filter(student=student).exists():
        raise ValidationError(
            "Student is already a member of this group."
        )

    if group.max_students is not None:
        current_count = active_memberships.count()

        if current_count >= group.max_students:
            raise ValidationError(
                "The group has reached its maximum capacity."
            )

    membership = GroupMembership(group=group, student=student)

    membership.full_clean()
    membership.save()

    return membership


@transaction.atomic
def leave_student_from_group(*, workspace, group_id, student_id):
    student = Student.objects.select_for_update().get(
            id=student_id,
            workspace=workspace
        )
    

    group = Group.objects.select_for_update().get(
            id=group_id,
            workspace=workspace
        )

    membership = GroupMembership.objects.select_for_update().get(
            group=group,
            student=student,
            left_at__isnull=True
        )
    

    membership.left_at = timezone.now()

    membership.full_clean()

    membership.save(update_fields=["left_at"])

    return membership