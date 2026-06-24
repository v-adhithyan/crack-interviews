from .base import *

DEBUG = False

STATIC_ROOT = Path(BASE_DIR / 'static')

HACKERLEAP_CODE = 'https://code.hackerleap.com'

JAVA_RELEASE = int(os.getenv("JAVA_RELEASE", "8"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE"),
        "USER": os.getenv("MYSQL_USER"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD"),
        "HOST": os.getenv("MYSQL_HOST"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
