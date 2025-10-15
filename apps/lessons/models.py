from django.db import models

import uuid

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone


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
            )
        ]

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