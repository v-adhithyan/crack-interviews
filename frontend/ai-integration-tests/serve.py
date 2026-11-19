"""Serve the Django portal against an isolated browser-test database."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path.cwd()))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

with TemporaryDirectory() as directory:
    settings.DATABASES["default"]["NAME"] = Path(directory) / "ai-integration.sqlite3"
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    settings.AI_USE_SHARED_KEY_FOR_LOCAL_DEV = False
    settings.HACKERLEAP_AI_MODE = "chatgpt"
    settings.MEDIA_ROOT = Path(directory) / "media"
    settings.SECRET_KEY = "isolated-browser-tests-django-secret"
    django.setup()
    call_command("migrate", verbosity=0)

    from apps.website.models import EarlyAccessUser

    user = get_user_model().objects.create_user(
        "portal-test", "portal-test@example.com", "browser-test-password",
    )
    EarlyAccessUser.objects.create(user=user, email=user.email, is_beta_active=True)
    get_user_model().objects.create_user(
        "staff-test", "staff-test@example.com", "browser-test-password", is_staff=True,
    )
    call_command("runserver", "127.0.0.1:8102", use_reloader=False)
