import uuid

from django.db import models
from django.db.models.functions import Lower
from django.core.exceptions import ValidationError
from django.utils import timezone

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