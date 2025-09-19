from django import forms 
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User

class TeacherRegistrationForm(forms.Form):
    email = forms.EmailField(max_length=254)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    workspace_name = forms.CharField(max_length=150, required=False)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        if password1:
            user = User(
                email = cleaned_data.get("email", ""),
                first_name = cleaned_data.get("first_name", ""),
                last_name = cleaned_data.get("last_name", "")
                )

            try:
                validate_password(password1, user=user)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data