from django import forms

from .models import Subject, Group

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("name", "description")

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.workspace = workspace

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        queryset = Subject.objects.filter(workspace=self.workspace, name__iexact=name)

        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError("A subject with this name already exists.")

        return name


class GroupBaseForm(forms.ModelForm):

    class Meta:
        model = Group

        fields = ("name", "description", "max_students")

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4
                }
            )
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if not name:
            raise forms.ValidationError(
                "Group name cannot be empty."
            )

        return name


class GroupCreateForm(GroupBaseForm):

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        label="Subject"
    )

    class Meta(GroupBaseForm.Meta):
        fields = ("name", "subject", "description", "max_students")

    def __init__(self, *args, workspace, **kwargs,):
        super().__init__(*args, **kwargs)

        self.fields["subject"].queryset = (
            Subject.objects
            .filter(
                workspace=workspace,
                is_active=True
            )
            .order_by("name")
        )


class GroupEditForm(GroupBaseForm):
    pass