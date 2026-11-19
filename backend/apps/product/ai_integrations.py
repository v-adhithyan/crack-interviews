import base64
import hmac

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .decorators import product_access_required
from .models import AIIntegration


def uses_shared_openai_key(user):
    return (
        settings.AI_USE_SHARED_KEY_FOR_LOCAL_DEV
        or user.is_staff
        or user.email.lower().endswith("@hackerleap.com")
    )


def _cipher():
    secrets = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    if secrets[0] == "dev-secret-key-change-me" and not settings.AI_USE_SHARED_KEY_FOR_LOCAL_DEV:
        raise ImproperlyConfigured("AI integration storage is unavailable. Contact support.")
    return MultiFernet([
        Fernet(base64.urlsafe_b64encode(hmac.digest(secret.encode(), b"product.ai-integration.v1", "sha256")))
        for secret in secrets if secret != "dev-secret-key-change-me" or settings.AI_USE_SHARED_KEY_FOR_LOCAL_DEV
    ])


def get_openai_api_key(user):
    if uses_shared_openai_key(user):
        if not settings.OPENAI_API_KEY:
            raise ImproperlyConfigured("OPENAI_API_KEY is required for this feature.")
        return settings.OPENAI_API_KEY

    integration = AIIntegration.objects.filter(user=user).first()
    if integration:
        try:
            return _cipher().decrypt(integration.encrypted_api_key.encode()).decode()
        except InvalidToken:
            pass
    raise ImproperlyConfigured("Set your ChatGPT API key in Settings → Integrations → AI to use this feature.")


class AIIntegrationForm(forms.Form):
    provider = forms.ChoiceField(choices=[("chatgpt", "ChatGPT"), ("claude", "Claude")])
    api_key = forms.CharField(label="API key", max_length=512, widget=forms.PasswordInput(
        attrs={"autocomplete": "new-password", "aria-describedby": "key-help"},
    ))

    def clean_provider(self):
        provider = self.cleaned_data["provider"]
        if provider != "chatgpt":
            raise forms.ValidationError("Claude is currently unsupported. Choose ChatGPT.")
        return provider

    def clean_api_key(self):
        key = self.cleaned_data["api_key"]
        if not key.isascii() or not key.isprintable() or any(character.isspace() for character in key):
            raise forms.ValidationError("Enter a valid API key without spaces.")
        return key


@sensitive_post_parameters("api_key")
@never_cache
@product_access_required
@require_http_methods(["GET", "POST"])
def ai_settings(request):
    shared = uses_shared_openai_key(request.user)
    form = AIIntegrationForm(request.POST if request.method == "POST" and not shared else None)
    if form.is_bound and form.is_valid():
        try:
            encrypted_key = _cipher().encrypt(form.cleaned_data["api_key"].encode()).decode()
        except ImproperlyConfigured as exc:
            form.add_error(None, str(exc))
        else:
            AIIntegration.objects.update_or_create(user=request.user, defaults={"encrypted_api_key": encrypted_key})
            messages.success(request, "ChatGPT API key saved.")
            return redirect("ai_integration_settings")

    return render(request, "product/ai_settings.html", {
        "form": form,
        "shared": shared,
        "configured": not shared and AIIntegration.objects.filter(user=request.user).exists(),
    })
