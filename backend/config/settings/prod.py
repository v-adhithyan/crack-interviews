from .base import *

DEBUG = False

STORAGES["staticfiles"] = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}

HACKERLEAP_CODE = os.getenv("HACKERLEAP_CODE", "https://code.hackerleap.com")

# Prefer PythonAnywhere's Java 11 toolchain when it is installed. Fall back to
# the system PATH (and Java 8 source compatibility) on other production hosts.
_JAVA11_HOME = "/usr/lib/jvm/java-11-openjdk-amd64/bin"
_JAVA11 = os.path.join(_JAVA11_HOME, "java")
_JAVAC11 = os.path.join(_JAVA11_HOME, "javac")
_HAS_JAVA11_TOOLCHAIN = os.path.isfile(_JAVA11) and os.path.isfile(_JAVAC11)

JAVA_EXECUTABLE = os.getenv("JAVA_EXECUTABLE", _JAVA11 if _HAS_JAVA11_TOOLCHAIN else JAVA_EXECUTABLE)
JAVAC_EXECUTABLE = os.getenv("JAVAC_EXECUTABLE", _JAVAC11 if _HAS_JAVA11_TOOLCHAIN else JAVAC_EXECUTABLE)
JAVA_RELEASE = int(os.getenv("JAVA_RELEASE", "11" if _HAS_JAVA11_TOOLCHAIN else "8"))

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
