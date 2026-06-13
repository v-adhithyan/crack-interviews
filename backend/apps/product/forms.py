import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError


class ProductLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "Enter your email"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Enter your password"}),
    )

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        password = self.cleaned_data.get("password")

        if identifier and password:
            username = identifier
            if "@" in identifier:
                user_model = get_user_model()
                user = user_model.objects.filter(email__iexact=identifier).first()
                if user:
                    username = user.get_username()

            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class EarlyAccessSignupForm(UserCreationForm):
    email = forms.EmailField(disabled=True)
    date_of_birth = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )

    class Meta:
        model = get_user_model()
        fields = ("email", "password1", "password2")

    def __init__(self, *args, early_access_user=None, **kwargs):
        self.early_access_user = early_access_user
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = early_access_user.email if early_access_user else ""
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password", "data-password-input": "true"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password"})

    def clean_email(self):
        if not self.early_access_user:
            raise ValidationError("This signup link is not valid.")
        return self.early_access_user.email.strip().lower()

    def clean_password1(self):
        password = self.cleaned_data.get("password1", "")
        checks = (
            (len(password) >= 8, "Password must be at least 8 characters."),
            (bool(re.search(r"[A-Z]", password)), "Password must include at least one uppercase letter."),
            (bool(re.search(r"[a-z]", password)), "Password must include at least one lowercase letter."),
            (bool(re.search(r"[0-9]", password)), "Password must include at least one number."),
            (bool(re.search(r"[^A-Za-z0-9]", password)), "Password must include at least one symbol."),
        )
        errors = [message for passed, message in checks if not passed]
        if errors:
            raise ValidationError(errors)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email
        if commit:
            user.save()
        return user
