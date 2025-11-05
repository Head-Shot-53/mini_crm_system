from django import forms

from apps.academics.models import Group, Subject
from apps.lessons.models import Lesson
from apps.students.models import Student


class BaseAssignmentDraftForm(forms.Form):
    subject = forms.ModelChoiceField(queryset=Subject.objects.none())

    lesson = forms.ModelChoiceField(
        queryset=Lesson.objects.none(),
        required=False
    )

    title = forms.CharField(max_length=255)

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 8}
        )
    )

    due_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}
        )
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)

        self.workspace = workspace

        self.fields["subject"].queryset = (
            Subject.objects
            .filter(
                workspace=workspace,
                is_active=True
            )
            .order_by("name")
        )

        self.fields["lesson"].queryset = (
            Lesson.objects
            .filter(workspace=workspace)
            .select_related(
                "subject",
                "student",
                "group"
            )
            .order_by("-start_at")
        )


class IndividualAssignmentDraftForm(BaseAssignmentDraftForm):
    student = forms.ModelChoiceField(queryset=Student.objects.none())

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, workspace=workspace, **kwargs)

        self.fields["student"].queryset = (
            Student.objects
            .filter(
                workspace=workspace,
                status=Student.Status.ACTIVE
            )
            .order_by(
                "last_name",
                "first_name"
            )
        )


class GroupAssignmentDraftForm(BaseAssignmentDraftForm):
    group = forms.ModelChoiceField(queryset=Group.objects.none())

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args,  workspace=workspace, **kwargs)

        self.fields["group"].queryset = (
            Group.objects
            .filter(
                workspace=workspace,
                is_active=True
            )
            .select_related("subject")
            .order_by("name")
        )