from django import forms 
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from decimal import Decimal
from zoneinfo import available_timezones

from .models import User, TeacherProfile

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


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")


class TeacherProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=[
            (timezone_name, timezone_name)
            for timezone_name in sorted(available_timezones())
        ]
    )

    class Meta:
        model = TeacherProfile
        fields = (
            "avatar",
            'bio',
            'timezone',
            'language',
            'currency',
            'default_lesson_duration',
            'default_lesson_price',
        )

    def clean_language(self):
        language = self.cleaned_data["language"].strip().lower()

        if len(language) not in (2,5):
            raise forms.ValidationError("Enter a valid language code, for example: pl, en, uk.")

        return language

    def clean_currency(self):
        currency = self.cleaned_data['currency'].strip().upper()

        if len(currency) != 3 or not currency.isalpha():
            raise forms.ValidationError("Currency must be a 3-letter code, for example PLN or EUR.")

        return currency

    def clean_default_lesson_price(self):
        price = self.cleaned_data["default_lesson_price"]

        if price < Decimal("0.00"):
            raise forms.ValidationError("lesson price cannot be negative")

        return price