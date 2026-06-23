import re
import uuid
from pathlib import Path

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Resume
from .models import QuickRefreshNote
from .pdf import extract_pdf_text
from .services import parse_analysis_json


MAX_RESUME_SIZE = 1024 * 1024


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


class EarlyAccessSignupForm(forms.Form):
    email = forms.EmailField(disabled=True)
    date_of_birth = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-input": "true"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, early_access_user=None, **kwargs):
        self.early_access_user = early_access_user
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = early_access_user.email if early_access_user else ""

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

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        email = cleaned_data.get("email")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields did not match.")

        if email and get_user_model().objects.filter(email__iexact=email).exists():
            self.add_error("email", "An account already exists for this email address.")

        return cleaned_data

    def save(self, commit=True):
        email = self.cleaned_data["email"]
        return get_user_model().objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password1"],
        )


class ResumeUploadForm(forms.Form):
    resume = forms.FileField(
        label="Resume",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}),
        error_messages={"required": "Please choose a PDF resume to upload."},
    )

    def clean_resume(self):
        resume = self.cleaned_data["resume"]
        extension = Path(resume.name).suffix.lower()
        content_type = getattr(resume, "content_type", "")

        if extension != ".pdf" or content_type not in ("application/pdf", "application/x-pdf", ""):
            raise ValidationError("Please upload a PDF resume.")

        if resume.size > MAX_RESUME_SIZE:
            raise ValidationError("Please upload a PDF no larger than 1 MB.")

        try:
            self.parsed_text = extract_pdf_text(resume)
        except Exception as exc:
            raise ValidationError("We could not read text from this PDF. Please upload a text-based PDF resume.") from exc

        if not self.parsed_text:
            raise ValidationError("We could not find readable text in this PDF. Please upload a text-based PDF resume.")

        if hasattr(resume, "seek"):
            resume.seek(0)

        return resume

    def save(self, user):
        resume_file = self.cleaned_data["resume"]
        existing_resume = Resume.objects.filter(user=user).first()
        old_file = existing_resume.file if existing_resume else None

        resume, _ = Resume.objects.update_or_create(
            user=user,
            defaults={
                "uuid": uuid.uuid4(),
                "file": resume_file,
                "original_filename": resume_file.name,
                "content_type": getattr(resume_file, "content_type", "application/pdf") or "application/pdf",
                "size": resume_file.size,
                "parsed_text": self.parsed_text,
            },
        )

        if old_file and old_file.name != resume.file.name:
            old_file.delete(save=False)

        return resume


class AnalysisPromptForm(forms.Form):
    job_description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "maxlength": "12000",
                "placeholder": "Paste job description here...",
            }
        ),
        error_messages={"required": "Please paste the job description."},
    )


class AnalysisResultForm(forms.Form):
    analysis_json = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Paste the JSON result here..."}),
        error_messages={"required": "Please paste the JSON result."},
    )

    def clean_analysis_json(self):
        raw_json = self.cleaned_data["analysis_json"]
        self.parsed_json = parse_analysis_json(raw_json)
        return raw_json


class QuickRefreshNoteForm(forms.ModelForm):
    class Meta:
        model = QuickRefreshNote
        fields = ("content", "language")
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "autocomplete": "off",
                    "autocapitalize": "off",
                    "spellcheck": "false",
                    "placeholder": "Paste quick reference notes, snippets, JSON, SQL, or commands here...",
                }
            ),
            "language": forms.Select(),
        }
