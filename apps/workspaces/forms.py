from django import forms

from .models import Workspace

class WorkspaceSettingsForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ("name",)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if not name:
            raise forms.ValidationError("Workspace name cannot be empty.")

        return name