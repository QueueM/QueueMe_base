"""
Queue Me – shared Django settings (development, staging, production).

Environment-specific values **must** come from the environment (.env or real env
vars).  Do not hard-code credentials or hostnames in this file.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import dj_database_url
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & dotenv
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")  # silently no-op if file is absent

TESTING = any(
    cmd in sys.argv for cmd in ("test", "pytest", "makemigrations", "migrate")
)


# ---------------------------------------------------------------------------
# Tiny helper – read env with “required” flag
# ---------------------------------------------------------------------------
def env(key: str, default: Optional[str] = None, *, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(
            f"⚠️  The environment variable {key} is required but not set."
        )
    return val


# ---------------------------------------------------------------------------
# Core toggles
# ---------------------------------------------------------------------------
SECRET_KEY: str = env("SECRET_KEY", required=True)
DEBUG: bool = env("DEBUG", "False").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS: list[str] = env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# ---------------------------------------------------------------------------
# Database – PostgreSQL everywhere
# ---------------------------------------------------------------------------
DEFAULT_PG_URL = (
    f"postgres://{env('POSTGRES_USER', 'queueme')}:{env('POSTGRES_PASSWORD', 'queueme')}"
    f"@{env('POSTGRES_HOST', 'localhost')}:{env('POSTGRES_PORT', '5432')}/{env('POSTGRES_DB', 'queueme')}"
)

DATABASES: dict[str, Any] = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", DEFAULT_PG_URL),
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
        ssl_require=env("DB_SSL_REQUIRE", "False").lower() in {"1", "true"},
    )
}


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    'django.contrib.gis',
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_yasg",
    "channels",
    "django_celery_beat",
    "django_celery_results",
    "django_filters",
    "storages",
    # Core apps
    "core",
    "algorithms",
    "websockets",
    # Queue Me domain apps  (order matters for FK / signals)
    "apps.authapp",
    "apps.rolesapp",
    "apps.geoapp",
    "apps.companiesapp",
    "apps.shopapp",
    "apps.employeeapp",
    "apps.specialistsapp",
    "apps.categoriesapp",
    "apps.serviceapp",
    "apps.packageapp",
    "apps.bookingapp",
    "apps.queueapp",
    "apps.reviewapp",
    "apps.customersapp",
    "apps.discountapp",
    "apps.payment",
    "apps.notificationsapp",
    "apps.chatapp",
    "apps.subscriptionapp",
    "apps.followapp",
    "apps.reelsapp",
    "apps.storiesapp",
    "apps.reportanalyticsapp",
    "apps.queueMeAdminApp",
    "apps.shopDashboardApp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "queueme.middleware.localization_middleware.LocalizationMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "queueme.middleware.auth_middleware.JWTAuthMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "queueme.middleware.performance_middleware.PerformanceMiddleware",
]

ROOT_URLCONF = "queueme.urls"
WSGI_APPLICATION = "queueme.wsgi.application"
ASGI_APPLICATION = "queueme.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Custom user model & auth backends
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "authapp.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.authapp.backends.PhoneNumberBackend",
]


# ---------------------------------------------------------------------------
# REST Framework & JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "utils.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "EXCEPTION_HANDLER": "utils.error_views.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "otp": "5/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------
JWT_COOKIE_NAME = "queueme_auth"
JWT_COOKIE_SECURE = not DEBUG
JWT_COOKIE_HTTPONLY = True
JWT_COOKIE_SAMESITE = "Lax"


# ---------------------------------------------------------------------------
# Channels – Redis
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(env("REDIS_HOST", "redis"), int(env("REDIS_PORT", "6379")))],
        },
    },
}


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_TIMEZONE = "Asia/Riyadh"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_RESULT_EXTENDED = True


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://redis:6379/1"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}


# ---------------------------------------------------------------------------
# I18N / L10N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
TIME_ZONE = env("TIME_ZONE", "Asia/Riyadh")
USE_I18N = True
USE_L10N = True
USE_TZ = True
LANGUAGES = [("en", "English"), ("ar", "Arabic")]
LOCALE_PATHS = [BASE_DIR / "locale"]


# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Use S3 for media if all creds present
if all(
    env(v)
    for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME")
):
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "me-south-1")
    AWS_S3_CUSTOM_DOMAIN = (
        f"{env('AWS_STORAGE_BUCKET_NAME')}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    )
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@queueme.net")


# ---------------------------------------------------------------------------
# Third-party integrations
# ---------------------------------------------------------------------------
MOYASAR_API_KEY = env("MOYASAR_API_KEY")
MOYASAR_WEBHOOK_SECRET = env("MOYASAR_WEBHOOK_SECRET")

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER")

SMS_BACKEND = "utils.sms.backends.twilio.TwilioBackend"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "https://queueme.net",
    "https://shop.queueme.net",
    "https://admin.queueme.net",
]
if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
CORS_ALLOW_ALL_ORIGINS = DEBUG  # easiest for local dev


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", "0") == "1"
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", "0") == "1"
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", "0") == "1"


# ---------------------------------------------------------------------------
# Default PK
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "filters": {
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "queueme.log",
            "formatter": "verbose",
        },
        "performance_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "performance.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "queueme": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.performance": {
            "handlers": ["console", "performance_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Front-end URLs
# ---------------------------------------------------------------------------
FRONTEND_URL = env("FRONTEND_URL", "https://queueme.net")
SHOP_PANEL_URL = env("SHOP_PANEL_URL", "https://shop.queueme.net")
ADMIN_PANEL_URL = env("ADMIN_PANEL_URL", "https://admin.queueme.net")


print(f"🏗️  Settings loaded  |  DEBUG={DEBUG}  |  DB={DATABASES['default']['ENGINE']}")
print(f"📦  Installed apps: {', '.join(INSTALLED_APPS)}")
