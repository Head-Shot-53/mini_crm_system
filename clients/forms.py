from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    class meta:
        model = Client
        fields = ['name', 'email', 'phone', 'company', 'status']
        