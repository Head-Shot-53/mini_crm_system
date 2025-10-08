import uuid

from django.db import models
from django.db.models.functions import Lower, Trim
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import Q, F

from apps.workspaces.models import Workspace


class Subject(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)

    workspace = models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name="subjects")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "workspace",
                name="unique_subject_name_per_workspace_ci",
            ),
        ]

        indexes = [
            models.Index(
                fields=("workspace", "is_active"),
                name="subject_workspace_active_idx",
            ),
        ]

    def __str__(self):
        return self.name


class StudentSubject(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="subject_enrollments")

    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="student_enrollments")

    started_on = models.DateField(default=timezone.localdate)
    level = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("started_on", "id")

        constraints = [
            models.UniqueConstraint(
                fields=("student", "subject"),
                name="unique_student_subject_pair"
            )
        ]

    def clean(self):
        super().clean()

        if self.student_id and self.subject_id:
            if self.student.workspace_id != self.subject.workspace_id:
                raise ValidationError({
                    "subject" : "Student and subject must belong to the same workspace"
                })

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name}"


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="teaching_groups")

    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="teaching_groups")

    students = models.ManyToManyField("students.Student",
        through="academics.GroupMembership",
        through_fields=("group", "student"),
        related_name="study_groups",
        blank=True
    )

    name = models.CharField(max_length=150)

    description = models.TextField(blank=True)

    max_students = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id",)

        constraints = [
            models.UniqueConstraint(
                Lower(Trim("name")),
                "workspace",
                name="unique_group_name_per_ws_ci"
            ),

            models.CheckConstraint(
                condition=(
                    Q(max_students__isnull=True)
                    | Q(max_students__gte=1)
                ),
                name="group_max_students_positive"
            )
        ]

        indexes = [
            models.Index(
                fields=(
                    "workspace",
                    "is_active"
                ),
                name="group_ws_active_idx"
            )
        ]

    def clean(self):
        super().clean()

        self.name = self.name.strip()

        if not self.name:
            raise ValidationError({
                "name": "Group name cannot be empty."
            })

        if self.workspace_id and self.subject_id:

            if self.subject.workspace_id != self.workspace_id:
                raise ValidationError({
                    "subject": (
                        "Group and subject must belong "
                        "to the same workspace."
                    )
                })

            if self._state.adding and not self.subject.is_active:
                raise ValidationError({
                    "subject": (
                        "Cannot create a group "
                        "with an inactive subject."
                    )
                })

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="memberships")

    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="group_memberships")

    joined_at = models.DateTimeField(default=timezone.now)

    left_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-joined_at", "id")

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "group",
                    "student"
                ),
                condition=Q(
                    left_at__isnull=True,
                ),
                name="unique_active_group_member"
            ),

            models.CheckConstraint(
                condition=(
                    Q(left_at__isnull=True)
                    | Q(left_at__gte=F("joined_at"))
                ),
                name="group_member_valid_dates"
            )
        ]

        indexes = [
            models.Index(
                fields=(
                    "group",
                    "left_at"
                ),
                name="gm_group_left_idx"
            )
        ]

    def clean(self):
        super().clean()

        if self.group_id and self.student_id:
            if (
                self.group.workspace_id
                != self.student.workspace_id
            ):
                raise ValidationError(
                    "Group and student must belong "
                    "to the same workspace."
                )

        if self.left_at and self.joined_at:
            if self.left_at < self.joined_at:
                raise ValidationError(
                    {
                        "left_at": (
                            "Leaving date cannot be earlier "
                            "than joining date."
                        )
                    }
                )

    @property
    def is_active(self):
        return self.left_at is None

    def __str__(self):
        return f"{self.student.full_name} - {self.group.name}"
