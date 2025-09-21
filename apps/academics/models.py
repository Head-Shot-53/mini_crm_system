import uuid

from django.db import models
from django.db.models.functions import Lower

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