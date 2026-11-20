"""Serve Django admin with a temporary database and a local test user."""
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
    settings.DATABASES["default"]["NAME"] = Path(directory) / "admin.sqlite3"
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    django.setup()
    call_command("migrate", verbosity=0)
    get_user_model().objects.create_superuser(
        username="admin-browser", password="local-test-password"
    )
    call_command("runserver", "127.0.0.1:8133", use_reloader=False)
