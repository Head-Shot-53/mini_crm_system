from django.db import models

import uuid

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone
from django.conf import settings


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


class AssignmentSubmission(models.Model):

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    recipient = models.OneToOneField(
        AssignmentRecipient,
        on_delete=models.PROTECT,
        related_name="submission"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED
    )

    is_late = models.BooleanField(default=False)

    first_submitted_at = models.DateTimeField()

    last_submitted_at = models.DateTimeField()

    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_homework_submissions",
        null=True,
        blank=True
    )

    teacher_feedback = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_submitted_at", "id")

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["submitted", "reviewed"]),
                name="hw_submission_valid_status"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    last_submitted_at__gte=models.F("first_submitted_at")),
                name="hw_submission_valid_times"
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="submitted",
                        reviewed_at__isnull=True,
                        reviewed_by__isnull=True
                    )
                    |
                    models.Q(
                        status="reviewed",
                        reviewed_at__isnull=False,
                        reviewed_by__isnull=False
                    )
                ),
                name="hw_submission_review_state"
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "status",
                    "last_submitted_at"
                ),
                name="hw_sub_status_time_idx"
            )
        ]

    @property
    def display_status(self):

        if self.status == self.Status.REVIEWED:
            return "reviewed"

        if self.is_late:
            return "late"

        return "submitted"


    def clean(self):
        super().clean()

        errors = {}

        assignment = self.recipient.assignment
        student = self.recipient.student

        if assignment.workspace_id != student.workspace_id:
            errors["recipient"] = (
                "Submission recipient belongs "
                "to another workspace."
            )

        if assignment.status == Assignment.Status.DRAFT:
            errors["recipient"] = (
                "Draft assignments cannot "
                "have submissions."
            )

        if (
            self.first_submitted_at
            and timezone.is_naive(self.first_submitted_at)
        ):
            errors["first_submitted_at"] = (
                "First submitted at must be timezone-aware."
            )

        if (
            self.last_submitted_at
            and timezone.is_naive(self.last_submitted_at)
        ):
            errors["last_submitted_at"] = (
                "Last submitted at must be timezone-aware."
            )

        if self.last_submitted_at  < self.first_submitted_at:
            errors["last_submitted_at"] = (
                "Last submission cannot be earlier "
                "than the first submission."
            )

        if self.reviewed_by_id:

            if self.reviewed_by_id  != assignment.workspace.owner_id:
                errors["reviewed_by"] = (
                    "Submission must be reviewed "
                    "by the workspace owner."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.recipient.student.full_name} — "
            f"{self.recipient.assignment.title}"
        )


class AssignmentSubmissionAttempt(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.PROTECT,
        related_name="attempts"
    )

    revision = models.PositiveIntegerField()

    answer_text = models.TextField(blank=True, default="")

    answer_url = models.URLField(
        blank=True,
        default="",
        max_length=500
    )

    submitted_at = models.DateTimeField()

    is_late = models.BooleanField(default=False)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_homework_attempts",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-revision", "id")

        constraints = [
            models.UniqueConstraint(
                fields=("submission", "revision"),
                name="hw_unique_submission_revision"
            ),

            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="hw_attempt_positive_revision"
            ),

            models.CheckConstraint(
                condition=(
                    ~models.Q(answer_text="")
                    |
                    ~models.Q(answer_url="")
                ),
                name="hw_attempt_has_content"
            )
        ]

        indexes = [
            models.Index(
                fields=(
                    "submission",
                    "submitted_at"
                ),
                name="hw_attempt_sub_time_idx"
            )
        ]

    def clean(self):
        super().clean()

        errors = {}

        self.answer_text = (self.answer_text or "").strip()

        self.answer_url = (self.answer_url or "").strip()

        if not self.answer_text and not self.answer_url:
            errors["__all__"] = (
                "Submission must contain text "
                "or a URL."
            )

        if self.revision < 1:
            errors["revision"] = (
                "Revision must be at least 1."
            )

        if timezone.is_naive(self.submitted_at):
            errors["submitted_at"] = (
                "Submission time must be timezone-aware."
            )

        if self.recorded_by_id:

            workspace = (self.submission.recipient.assignment.workspace)

            if self.recorded_by_id != workspace.owner_id:
                errors["recorded_by"] = (
                    "Submission must be recorded "
                    "by the workspace owner in V1."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.submission} — revision {self.revision}"
        