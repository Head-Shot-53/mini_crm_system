from django import forms

from .models import Subject

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