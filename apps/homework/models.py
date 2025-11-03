from django.db import models

import uuid

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone


class Assignment(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.PROTECT,
        related_name="assignments"
    )

    lesson = models.ForeignKey(
        "lessons.Lesson",
        on_delete=models.PROTECT,
        related_name="assignments",
        null=True,
        blank=True
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="individual_assignments",
        null=True,
        blank=True
    )

    group = models.ForeignKey(
        "academics.Group",
        on_delete=models.PROTECT,
        related_name="assignments",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    due_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "id")

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        student__isnull=False,
                        group__isnull=True
                    )
                    |
                    Q(
                        student__isnull=True,
                        group__isnull=False
                    )
                ),
                name="hw_assignment_one_target"
            ),

            models.CheckConstraint(
                condition=(
                    Q(
                        status="draft",
                        published_at__isnull=True
                    )
                    |
                    Q(status__in=[
                            "published",
                            "closed"
                        ],
                        published_at__isnull=False,
                        due_at__isnull=False
                    )
                ),
                name="hw_assignment_publication_state"
            ),

            models.CheckConstraint(
                condition=(
                    Q(due_at__isnull=True)
                    |
                    Q(published_at__isnull=True)
                    |
                    Q(due_at__gt=F("published_at"))
                ),
                name="hw_assignment_due_after_publish"
            )
        ]

        indexes = [
            models.Index(
                fields=(
                    "workspace",
                    "status",
                    "due_at"
                ),
                name="hw_ws_status_due_idx"
            ),

            models.Index(
                fields=(
                    "workspace",
                    "created_at"
                ),
                name="hw_ws_created_idx"
            )
        ]

    @property
    def assignment_type(self):
        if self.group_id is not None:
            return "group"

        return "individual"


    def clean(self):
        super().clean()

        errors = {}

        self.title = (self.title or "").strip()

        if not self.title:
            errors["title"] = (
                "Assignment title cannot be empty."
            )

        if bool(self.student_id) == bool(self.group_id):
            errors["__all__"] = (
                "Assignment must target exactly "
                "one student or one group."
            )

        if self.due_at is not None:
            if timezone.is_naive(self.due_at):
                errors["due_at"] = (
                    "Deadline must be timezone-aware."
                )

        if self.workspace_id and self.subject_id:
            if self.subject.workspace_id != self.workspace_id:
                errors["subject"] = (
                    "Subject belongs to another workspace."
                )

        if self.workspace_id and self.student_id:
            if self.student.workspace_id != self.workspace_id:
                errors["student"] = (
                    "Student belongs to another workspace."
                )

        if self.group_id:
            group = self.group

            if self.workspace_id and group.workspace_id != self.workspace_id:
                errors["group"] = (
                    "Group belongs to another workspace."
                )

            if self.subject_id  and group.subject_id != self.subject_id:
                errors["subject"] = (
                    "Assignment subject must match "
                    "the group's subject."
                )

        if self.lesson_id:
            lesson = self.lesson

            if self.workspace_id and lesson.workspace_id != self.workspace_id:
                errors["lesson"] = (
                    "Lesson belongs to another workspace."
                )

            elif self.subject_id and lesson.subject_id != self.subject_id:
                errors["lesson"] = (
                    "Assignment subject must match "
                    "the lesson's subject."
                )

            elif self.student_id:
                if lesson.student_id != self.student_id or lesson.group_id is not None:
                    errors["lesson"] = (
                        "Individual assignment must reference "
                        "a lesson for the selected student."
                    )

            elif self.group_id:
                if lesson.group_id != self.group_id or lesson.student_id is not None:
                    errors["lesson"] = (
                        "Group assignment must reference "
                        "a lesson for the selected group."
                    )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class AssignmentRecipient(models.Model):

    class Source(models.TextChoices):
        SNAPSHOT = "snapshot", "Publication snapshot"
        MANUAL = "manual", "Manual assignment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="recipients"
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="assignment_recipients"
    )

    group_membership = models.ForeignKey(
        "academics.GroupMembership",
        on_delete=models.PROTECT,
        related_name="assignment_recipients",
        null=True,
        blank=True
    )

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.SNAPSHOT)

    assigned_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name", "id")

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "assignment",
                    "student"
                ),
                name="hw_unique_assignment_recipient"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    source__in=[
                        "snapshot",
                        "manual"
                    ],
                ),
                name="hw_recipient_valid_source"
            )
        ]

        indexes = [
            models.Index(
                fields=(
                    "student",
                    "assigned_at",
                ),
                name="hw_rec_student_time_idx"
            )
        ]

    def clean(self):
        super().clean()

        errors = {}

        assignment = self.assignment

        if assignment.workspace_id != self.student.workspace_id:
            errors["student"] = (
                "Recipient belongs to another workspace."
            )

        if assignment.published_at is None:
            errors["assignment"] = (
                "Recipients can only belong "
                "to a published assignment."
            )

        if assignment.published_at is not None and self.assigned_at < assignment.published_at:
            errors["assigned_at"] = (
                "Recipient cannot be assigned "
                "before assignment publication."
            )

        if assignment.student_id is not None:

            if self.student_id != assignment.student_id:
                errors["student"] = (
                    "Individual assignment recipient "
                    "must match the assignment student."
                )

            if self.group_membership_id is not None:
                errors["group_membership"] = (
                    "Individual assignment cannot "
                    "have a group membership."
                )

        elif assignment.group_id is not None:

            if self.group_membership_id is None:
                errors["group_membership"] = (
                    "Group assignment recipient requires "
                    "a group membership."
                )

            else:
                membership = self.group_membership

                if  membership.group_id  != assignment.group_id:
                    errors["group_membership"] = (
                        "Membership belongs "
                        "to another group."
                    )

                if  membership.student_id != self.student_id:
                    errors["group_membership"] = (
                        "Membership belongs "
                        "to another student."
                    )

                if membership.joined_at > self.assigned_at:
                    errors["group_membership"] = (
                        "Student joined the group "
                        "after assignment."
                    )

                if membership.left_at is not None and membership.left_at <= self.assigned_at:
                    errors["group_membership"] = (
                        "Student had already left "
                        "the group."
                    )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.assignment.title} — {self.student.full_name}"