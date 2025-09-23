from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.utils import timezone

from apps.workspaces.models import Workspace

import uuid

class Student(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="students")
    
    subjects = models.ManyToManyField(
        "academics.Subject",
        through="academics.StudentSubject",
        through_fields=("student", "subject"),
        related_name="students",
        blank=True
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    start_date = models.DateField(default=timezone.localdate)
    level = models.CharField(max_length=100, blank=True)
    default_lesson_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0),])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("last_name", "first_name", "id")
        indexes = [
            models.Index(
                fields=[
                    "workspace",
                    "status",
                ],
                name="student_ws_status_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(default_lesson_price__gte=0)
                    | Q(default_lesson_price__isnull=True)
                ),
                name="student_price_non_negative",
            ),
        ]

    @property
    def full_name(self):
        return (f"{self.first_name} {self.last_name}").strip()

    def __str__(self):
        return self.full_name