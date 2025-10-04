from django import forms

from .models import Student

from django.utils import timezone

from apps.academics.models import Subject, StudentSubject
from apps.academics.services import ENROLLMENT_STATUS_TRANSITIONS


class StudentForm(forms.ModelForm):

    class Meta:
        model = Student

        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "start_date",
            "default_lesson_price",
        )

        widgets = {
            "start_date": forms.DateInput(
                attrs={
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
        }

    def clean_first_name(self):
        first_name = self.cleaned_data["first_name"].strip()

        if not first_name:
            raise forms.ValidationError(
                "First name cannot be empty."
            )

        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data["last_name"].strip()

        if not last_name:
            raise forms.ValidationError(
                "Last name cannot be empty."
            )

        return last_name

    def clean_email(self):
        email = self.cleaned_data.get("email", "")

        return email.strip().lower()


class SubjectAssignmentForm(forms.Form):

    subject = forms.ModelChoiceField(queryset=Subject.objects.none(),label="Subject")

    level = forms.CharField(max_length=100,required=False)

    started_on = forms.DateField(
        required=False,
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            },
            format="%Y-%m-%d",
        ),
    )

    def __init__(self,*args,workspace,student,**kwargs):
        super().__init__(*args, **kwargs)

        assigned_subject_ids = (
            StudentSubject.objects
            .filter(student=student)
            .values("subject_id")
        )

        self.fields["subject"].queryset = (
            Subject.objects
            .filter(
                workspace=workspace,
                is_active=True,
            )
            .exclude(
                id__in=assigned_subject_ids,
            ).order_by("name")
        )


class StudentFilterForm(forms.Form):

    q = forms.CharField(required=False,max_length=100,label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Name, email or phone"
            }
        )
    )

    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All statuses"),
            *[
                choice
                for choice in Student.Status.choices
                if choice[0] != Student.Status.ARCHIVED
            ]
        ]
    )

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        empty_label="All subjects"
    )

    def __init__(self, *args, workspace, archived=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["subject"].queryset = (
            Subject.objects
            .filter(workspace=workspace)
            .order_by("name")
        )

        if archived:
            self.fields.pop("status")

    def clean_q(self):
        value = self.cleaned_data["q"]

        return " ".join(value.split())


class EnrollmentUpdateForm(forms.ModelForm):

    class Meta:
        model = StudentSubject

        fields = ("started_on", "level", "status", "notes")

        widgets = {
            "started_on": forms.DateInput(
                attrs={
                    "type": "date"
                },
                format="%Y-%m-%d"
            ),

            "notes": forms.Textarea(
                attrs={
                    "rows": 5
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_status = self.instance.status

        allowed_statuses = (
            ENROLLMENT_STATUS_TRANSITIONS.get(
                current_status,
                set(),
            )
        )

        available_statuses = allowed_statuses | {current_status}

        self.fields["status"].choices = [
            (value, label)
            for value, label in StudentSubject.Status.choices
            if value in available_statuses
        ]

    def clean_level(self):
        return self.cleaned_data["level"].strip()

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()