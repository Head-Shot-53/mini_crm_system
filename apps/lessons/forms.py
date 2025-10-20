from django import forms
from django.core.exceptions import ValidationError

from apps.academics.models import Group, StudentSubject, Subject

from apps.students.models import Student

from .timezone_utils import resolve_local_datetime


class LessonTimeForm(forms.Form):

    start_date = forms.DateField(
        label="Start date",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d"
        )
    )

    start_time = forms.TimeField(
        label="Start time",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            attrs={"type": "time"},
            format="%H:%M"
        )
    )

    end_date = forms.DateField(
        label="End date",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d"
        )
    )

    end_time = forms.TimeField(
        label="End time",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            attrs={"type": "time"},
            format="%H:%M"
        )
    )

    def clean(self):
        cleaned_data = super().clean()

        required_fields = ("start_date", "start_time", "end_date", "end_time")

        if any(
            cleaned_data.get(field) is None
            for field in required_fields
        ):
            return cleaned_data

        try:
            start_at = resolve_local_datetime(
                lesson_date=cleaned_data["start_date"],
                lesson_time=cleaned_data["start_time"]
            )

            end_at = resolve_local_datetime(
                lesson_date=cleaned_data["end_date"],
                lesson_time=cleaned_data["end_time"]
            )

        except ValidationError as error:
            raise forms.ValidationError(
                error.messages
            )

        if end_at <= start_at:
            raise forms.ValidationError(
                "Lesson end must be later "
                "than lesson start."
            )

        cleaned_data["start_at"] = start_at
        cleaned_data["end_at"] = end_at

        return cleaned_data


class IndividualLessonCreateForm(LessonTimeForm):

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        label="Student"
    )

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        label="Subject"
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4}
        )
    )

    field_order = ("student", "subject", "start_date", "start_time", "end_date", "end_time", "notes")

    def __init__(self, *args,  workspace, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["student"].queryset = (
            Student.objects
            .filter(
                workspace=workspace,
                status=Student.Status.ACTIVE
            )
            .order_by(
                "last_name",
                "first_name",
                "id"
            )
        )

        self.fields["subject"].queryset = (
            Subject.objects
            .filter(
                workspace=workspace,
                is_active=True
            )
            .order_by("name")
        )

    def clean(self):
        cleaned_data = super().clean()

        student = cleaned_data.get("student")
        subject = cleaned_data.get("subject")

        if student and subject:

            has_enrollment = (
                StudentSubject.objects
                .filter(
                    student=student,
                    subject=subject,
                    status=StudentSubject.Status.ACTIVE
                )
                .exists()
            )

            if not has_enrollment:
                self.add_error(
                    "subject",
                    "This student does not have "
                    "an active enrollment "
                    "in the selected subject."
                )

        return cleaned_data


class GroupLessonCreateForm(LessonTimeForm):

    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        label="Teaching group",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4}
        )
    )

    field_order = ("group", "start_date", "start_time", "end_date", "end_time", "notes")

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["group"].queryset = (
            Group.objects
            .filter(
                workspace=workspace,
                subject__workspace=workspace,
                is_active=True,
                subject__is_active=True
            )
            .select_related("subject")
            .order_by("name")
        )


class LessonRescheduleForm(LessonTimeForm):
    pass