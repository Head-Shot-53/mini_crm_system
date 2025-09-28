from django import forms

from .models import Student

from django.utils import timezone

from apps.academics.models import Subject, StudentSubject


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