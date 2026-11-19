"""Serve the real signup page with an isolated database for browser tests."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path.cwd()))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"

import django
from django.conf import settings
from django.core.management import call_command

with TemporaryDirectory() as directory:
    settings.DATABASES["default"]["NAME"] = Path(directory) / "signup.sqlite3"
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    django.setup()
    call_command("migrate", verbosity=0)

    from apps.product.models import PublicBuilderCounter
    from apps.product.public_resume_views import SIGNUP_COUNTER_KEY, signup_reset_at

    PublicBuilderCounter.objects.create(
        key=SIGNUP_COUNTER_KEY, count=9, expires_at=signup_reset_at(),
    )
    call_command("runserver", "127.0.0.1:8101", use_reloader=False)
