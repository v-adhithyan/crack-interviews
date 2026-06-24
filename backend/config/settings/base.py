from pathlib import Path
import os

from dotenv import load_dotenv

from config.compat import patch_django_context_copy_for_python_314

patch_django_context_copy_for_python_314()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_dotenv_override = os.getenv("DJANGO_DOTENV_OVERRIDE")
if _dotenv_override is None:
    _dotenv_override = str(os.getenv("DJANGO_SETTINGS_MODULE", "").endswith(".dev"))

load_dotenv(BASE_DIR / ".env", override=_dotenv_override.lower() in {"1", "true", "yes", "on"})

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_q",
    "rest_framework",
    "apps.core",
    "apps.website",
    "apps.product",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "product_dashboard"
LOGOUT_REDIRECT_URL = "home_page"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    if origin.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

PYTHON_EXECUTABLE = os.getenv("PYTHON_EXECUTABLE", "python3")
JAVA_EXECUTABLE = os.getenv("JAVA_EXECUTABLE", "java")
JAVAC_EXECUTABLE = os.getenv("JAVAC_EXECUTABLE", "javac")
JAVA_RELEASE = int(os.getenv("JAVA_RELEASE", "17"))
COMPILE_TIMEOUT_SECONDS = float(os.getenv("COMPILE_TIMEOUT_SECONDS", "8"))
CODE_TIMEOUT_SECONDS = float(os.getenv("CODE_TIMEOUT_SECONDS", "2"))

HACKERLEAP_AI_MODE = os.getenv("HACKERLEAP_AI_MODE", "manual").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

Q_CLUSTER = {
    "name": "HackerLeap",
    "workers": int(os.getenv("DJANGO_Q_WORKERS", "1")),
    "timeout": int(os.getenv("DJANGO_Q_TIMEOUT", "600")),
    "retry": int(os.getenv("DJANGO_Q_RETRY", "900")),
    "queue_limit": int(os.getenv("DJANGO_Q_QUEUE_LIMIT", "50")),
    "bulk": int(os.getenv("DJANGO_Q_BULK", "5")),
    "orm": os.getenv("DJANGO_Q_ORM", "default"),
}
