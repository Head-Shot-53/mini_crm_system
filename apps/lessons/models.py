from django.db import models

import uuid

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone
from django.conf import settings


from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeBoundary, RangeOperators

from .db_expressions import TsTzRange

class Lesson(models.Model):

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, related_name="lessons")

    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="lessons")

    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="individual_lessons", null=True, blank=True)

    group = models.ForeignKey("academics.Group", on_delete=models.PROTECT, related_name="group_lessons", null=True, blank=True)

    start_at = models.DateTimeField()

    end_at = models.DateTimeField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    attendance_initialized_at = models.DateTimeField(null=True, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)

    cancellation_reason = models.TextField(blank=True, default="")

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_at", "id")

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        student__isnull=False,
                        group__isnull=True
                    )
                    | Q(
                        student__isnull=True,
                        group__isnull=False
                    )
                ),
                name="lesson_exactly_one_target"
            ),

            models.CheckConstraint(
                condition=Q(
                    end_at__gt=F("start_at")
                ),
                name="lesson_valid_time_range"
            ),

            ExclusionConstraint(
                name="lesson_no_workspace_time_overlap",

                expressions=[
                    (
                        TsTzRange(
                            "start_at",
                            "end_at",
                            RangeBoundary()
                        ),
                        RangeOperators.OVERLAPS
                    ),

                    (
                        "workspace",
                        RangeOperators.EQUAL
                    )
                ],

                condition=Q(
                    status__in=[
                        "scheduled",
                        "completed"
                    ],
                )
            )
        ]

        models.CheckConstraint(
            condition=models.Q(
                status__in=[
                    "scheduled",
                    "completed",
                    "cancelled"
                ]
            ),
            name="lesson_valid_status"
        ),

        indexes = [
            models.Index(
                fields=(
                    "workspace",
                    "start_at"
                ),
                name="lesson_ws_start_idx"
            ),

            models.Index(
                fields=("workspace", "status", "start_at"),
                name="lesson_ws_status_start_idx"
            )
        ]

    @property
    def lesson_type(self):
        if self.group_id is not None:
            return "group"

        return "individual"

    @property
    def duration_minutes(self):
        if self.start_at is None or self.end_at is None:
            return None

        duration = self.end_at - self.start_at

        return duration.total_seconds() / 60

    def clean(self):
        super().clean()

        if bool(self.student_id) == bool(self.group_id):
            raise ValidationError(
                "A lesson must have exactly one "
                "student or one group."
            )

        if (
            isinstance(self.start_at, datetime)
            and isinstance(self.end_at, datetime)
            and (
                timezone.is_aware(self.start_at)
                == timezone.is_aware(self.end_at)
            )
            and self.end_at <= self.start_at
        ):
            raise ValidationError({
                "end_at": (
                    "Lesson end must be later "
                    "than lesson start."
                )
            })

        if self.subject_id and self.workspace_id:
            if self.subject.workspace_id != self.workspace_id:
                raise ValidationError({
                    "subject": (
                        "Subject and lesson must belong "
                        "to the same workspace."
                    )
                })

        if self.student_id and self.workspace_id:
            if self.student.workspace_id != self.workspace_id:
                raise ValidationError({
                    "student": (
                        "Student and lesson must belong "
                        "to the same workspace."
                    )
                })

        if self.group_id and self.workspace_id:
            if self.group.workspace_id != self.workspace_id:
                raise ValidationError({
                    "group": (
                        "Group and lesson must belong "
                        "to the same workspace."
                    )
                })

            if (
                self.subject_id
                and self.group.subject_id != self.subject_id
            ):
                raise ValidationError({
                    "subject": (
                        "Lesson subject must match "
                        "the group's subject."
                    )
                })

    def __str__(self):
        return (
            f"{self.subject.name} | "
            f"{self.start_at:%Y-%m-%d %H:%M}"
        )


class LessonAttendance(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="attendance_records")

    student = models.ForeignKey("students.Student",on_delete=models.PROTECT, related_name="lesson_attendances")

    group_membership = models.ForeignKey(
        "academics.GroupMembership",
        on_delete=models.PROTECT,
        related_name="lesson_attendances",
        null=True,
        blank=True
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    notes = models.TextField(blank=True, default="")

    recorded_at = models.DateTimeField(null=True, blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_attendances",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "student__last_name",
            "student__first_name",
            "id"
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "lesson",
                    "student"
                ],
                name="unique_lesson_attendance_student"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "present",
                        "absent",
                        "late",
                        "excused"
                    ],
                ),
                name="lesson_attendance_valid_status"
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="pending",
                        recorded_at__isnull=True,
                        recorded_by__isnull=True
                    )
                    |
                    (
                        models.Q(
                            status__in=[
                                "present",
                                "absent",
                                "late",
                                "excused"
                            ],
                        )
                        & models.Q(
                            recorded_at__isnull=False,
                            recorded_by__isnull=False
                        )
                    )
                ),
                name="attendance_recording_consistency"
            )
        ]

        indexes = [
            models.Index(
                fields=[
                    "lesson",
                    "status"
                ],
                name="attendance_lesson_status_idx"
            )
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.lesson_id and self.student_id:

            if (
                self.lesson.workspace_id
                != self.student.workspace_id
            ):
                errors["student"] = (
                    "Lesson and student must belong "
                    "to the same workspace."
                )

            if self.lesson.group_id is None:

                if self.lesson.student_id != self.student_id:
                    errors["student"] = (
                        "Individual attendance must "
                        "belong to the lesson's student."
                    )

                if self.group_membership_id is not None:
                    errors["group_membership"] = (
                        "Individual attendance cannot "
                        "have a group membership."
                    )

            else:

                if self.group_membership_id is None:
                    errors["group_membership"] = (
                        "Group attendance requires "
                        "a group membership."
                    )

                else:
                    membership = self.group_membership

                    if membership.group_id != self.lesson.group_id:
                        errors["group_membership"] = (
                            "Membership belongs "
                            "to another group."
                        )

                    if membership.student_id != self.student_id:
                        errors["group_membership"] = (
                            "Membership belongs "
                            "to another student."
                        )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.student.full_name} — {self.lesson.id}"