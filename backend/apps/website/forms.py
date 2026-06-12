from django import forms

from .models import EarlyAccessUser


class EarlyAccessForm(forms.ModelForm):
    email = forms.EmailField(
        error_messages={
            "invalid": "Please enter a valid email address.",
            "required": "Please enter your email address.",
        }
    )

    class Meta:
        model = EarlyAccessUser
        fields = ["email"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def validate_unique(self):
        return None
