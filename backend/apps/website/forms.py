from django import forms

from .models import EarlyAccessUser
from .models import PricingSuggestion


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


class PricingSuggestionForm(forms.ModelForm):
    price = forms.IntegerField(
        min_value=99,
        max_value=999,
        widget=forms.NumberInput(
            attrs={
                "type": "range",
                "min": "99",
                "max": "999",
                "step": "1",
                "class": "pricing-range",
            }
        ),
        error_messages={
            "min_value": "Please choose a price of at least ₹99.",
            "max_value": "Please choose a price no more than ₹999.",
            "invalid": "Please choose a valid price.",
            "required": "Please choose a price.",
        },
    )
    no_of_months = forms.IntegerField(
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(
            attrs={
                "type": "range",
                "min": "1",
                "max": "12",
                "step": "1",
                "class": "pricing-range",
            }
        ),
        error_messages={
            "min_value": "Please choose at least 1 month.",
            "max_value": "Please choose no more than 12 months.",
            "invalid": "Please choose a valid number of months.",
            "required": "Please choose the number of months.",
        },
    )

    class Meta:
        model = PricingSuggestion
        fields = ["price", "no_of_months"]
