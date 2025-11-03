from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import Group, GroupMembership, StudentSubject, Subject
from apps.students.models import Student

from apps.homework.models import Assignment, AssignmentRecipient


@transaction.atomic
def publish_assignment(*, workspace, assignment_id):
    assignment = (
        Assignment.objects
        .select_for_update()
        .get(
            id=assignment_id,
            workspace=workspace
        )
    )

    if assignment.status != Assignment.Status.DRAFT:
        raise ValidationError(
            "Only draft assignments can be published."
        )

    published_at = timezone.now()

    if assignment.due_at is None:
        raise ValidationError(
            "Assignment deadline is required "
            "before publication."
        )

    if assignment.due_at <= published_at:
        raise ValidationError(
            "Assignment deadline must be "
            "later than publication time."
        )

    recipients = []

    if assignment.student_id is not None:

        student = (
            Student.objects
            .select_for_update()
            .get(
                id=assignment.student_id,
                workspace=workspace
            )
        )

        subject = (
            Subject.objects
            .select_for_update()
            .get(
                id=assignment.subject_id,
                workspace=workspace
            )
        )

        if student.status != Student.Status.ACTIVE:
            raise ValidationError(
                "Only active students can receive "
                "new individual assignments."
            )

        if not subject.is_active:
            raise ValidationError(
                "Cannot publish an assignment "
                "for an inactive subject."
            )

        has_active_enrollment = (
            StudentSubject.objects
            .filter(
                student=student,
                subject=subject,
                status=StudentSubject.Status.ACTIVE
            )
            .exists()
        )

        if not has_active_enrollment:
            raise ValidationError(
                "Student must have an active "
                "enrollment in this subject."
            )

        recipients.append(
            AssignmentRecipient(
                assignment=assignment,
                student=student,
                source=AssignmentRecipient.Source.SNAPSHOT,
                assigned_at=published_at
            )
        )

    else:

        group = (
            Group.objects
            .select_for_update()
            .get(
                id=assignment.group_id,
                workspace=workspace,
                subject_id=assignment.subject_id
            )
        )

        subject = (
            Subject.objects
            .select_for_update()
            .get(
                id=assignment.subject_id,
                workspace=workspace
            )
        )

        if not group.is_active:
            raise ValidationError(
                "Cannot publish an assignment "
                "for an inactive group."
            )

        if not subject.is_active:
            raise ValidationError(
                "Cannot publish an assignment "
                "for an inactive subject."
            )

        memberships = (
            GroupMembership.objects
            .filter(
                group=group,
                joined_at__lte=published_at
            )
            .filter(
                Q(left_at__isnull=True)
                | Q(left_at__gt=published_at)
            )
            .select_related("student")
            .order_by("student_id", "joined_at","id")
        )

        seen_students = set()

        for membership in memberships:

            student = membership.student

            if student.workspace_id != workspace.id:
                raise ValidationError(
                    "Cross-workspace group membership detected."
                )

            if student.status == Student.Status.ARCHIVED:
                raise ValidationError(
                    "Archived student has an active "
                    "group membership."
                )

            if student.id in seen_students:
                raise ValidationError(
                    "Overlapping active group membership "
                    "history detected."
                )

            seen_students.add(
                student.id
            )

            recipients.append(
                AssignmentRecipient(
                    assignment=assignment,
                    student=student,
                    group_membership=membership,
                    source=AssignmentRecipient.Source.SNAPSHOT,
                    assigned_at=published_at
                )
            )

        if not recipients:
            raise ValidationError(
                "Cannot publish an assignment "
                "to an empty group."
            )

    assignment.status = Assignment.Status.PUBLISHED
    assignment.published_at = published_at

    assignment.full_clean()

    assignment.save(
        update_fields=[
            "status",
            "published_at",
            "updated_at"
        ]
    )

    for recipient in recipients:
        recipient.full_clean()

    AssignmentRecipient.objects.bulk_create(recipients)

    return assignment