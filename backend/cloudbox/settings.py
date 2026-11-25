"""Django settings for CloudBox (Mini Dropbox) project."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.environ.get("VERCEL"))
WRITABLE_TMP_DIR = Path("/tmp/cloudbox") if IS_VERCEL else BASE_DIR

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "cloudbox-dev-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "accounts",
    "storage",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "cloudbox.db_sync.S3SqliteSyncMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cloudbox.urls"

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

WSGI_APPLICATION = "cloudbox.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()

if DATABASE_URL.startswith("mysql://") or DATABASE_URL.startswith("mysql2://"):
    parsed = urlparse(DATABASE_URL)
    db_options = {"charset": "utf8mb4"}
    if os.environ.get("MYSQL_SSL", "true").lower() == "true":
        db_options["ssl"] = {"ssl_mode": "PREFERRED"}
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "127.0.0.1",
            "PORT": str(parsed.port or 3306),
            "CONN_MAX_AGE": 60,
            "OPTIONS": db_options,
        }
    }
elif DB_ENGINE == "mysql":
    db_options = {"charset": "utf8mb4"}
    if os.environ.get("MYSQL_SSL", "false").lower() == "true":
        db_options["ssl"] = {"ssl_mode": "PREFERRED"}
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_DATABASE", "cloudbox"),
            "USER": os.environ.get("MYSQL_USER", "root"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": db_options,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": WRITABLE_TMP_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,https://cloudbox-mini-dropbox.vercel.app",
    ).split(",")
    if origin.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.SignedTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("THROTTLE_ANON_RATE", "120/minute"),
        "user": os.environ.get("THROTTLE_USER_RATE", "600/minute"),
    },
}

# Security hardening behind HTTPS proxy (Vercel)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Upload limits (supports files up to 100 MB directly via S3 presigned URLs)
MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", 100 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_STORAGE_QUOTA_BYTES = int(os.environ.get("DEFAULT_STORAGE_QUOTA_MB", 500)) * 1024 * 1024

# Cloud Storage configuration (AWS S3 Free Tier or local simulated bucket)
USE_S3 = os.environ.get("USE_S3", "false").lower() == "true"
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "cloudbox-mini-dropbox")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ap-south-1")

# AWS S3 Free Tier provides 5 GB Standard Storage; cap total bucket usage at 4.5 GB by default
S3_FREE_TIER_GUARD = os.environ.get("S3_FREE_TIER_GUARD", "true").lower() == "true"
S3_FREE_TIER_MAX_BYTES = int(
    float(os.environ.get("S3_FREE_TIER_MAX_GB", "4.5")) * 1024 * 1024 * 1024
)

LOCAL_BUCKET_DIR = Path(
    os.environ.get("LOCAL_BUCKET_DIR", WRITABLE_TMP_DIR / "media_bucket")
)
CHUNK_TEMP_DIR = Path(os.environ.get("CHUNK_TEMP_DIR", WRITABLE_TMP_DIR / "tmp_chunks"))
