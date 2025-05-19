"""
Queue Me – shared Django settings (development, staging, production).

Environment-specific values **must** come from the environment (.env or real env
vars). Do not hard-code credentials or hostnames in this file.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Optional

from decouple import config  # Use python-decouple for env vars
from django.utils.translation import gettext_lazy as _  # noqa: F401 - Used in LANGUAGES setting
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & dotenv
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load the appropriate .env file based on settings module
if "production" in os.environ.get("DJANGO_SETTINGS_MODULE", ""):
    load_dotenv(BASE_DIR / ".env.production")  # Load production .env if exists
else:
    load_dotenv(BASE_DIR / ".env")  # Load development .env if exists

TESTING = any(cmd in sys.argv for cmd in ("test", "pytest", "makemigrations", "migrate"))


# ---------------------------------------------------------------------------
# Tiny helper – read env with "required" flag
# ---------------------------------------------------------------------------
def env(key: str, default: Optional[str] = None, *, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"⚠️  The environment variable {key} is required but not set.")
    return val


# ---------------------------------------------------------------------------
# Core toggles
# ---------------------------------------------------------------------------
# SECURITY WARNING: keep the secret key used in production secret!
# Load SECRET_KEY from environment variable. Use a default ONLY for local dev if necessary,
# but ideally, set it in your .env file.
SECRET_KEY = config("SECRET_KEY", default="django-insecure-fallback-key-change-me-in-env")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=lambda v: [s.strip() for s in v.split(",")]
)

# ---------------------------------------------------------------------------
# Database – PostgreSQL everywhere
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "queueme"),
        "USER": os.environ.get("POSTGRES_USER", "queueme"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "queueme"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,  # Keep connections alive for 10 minutes
        "OPTIONS": {
            "connect_timeout": 10,
            "client_encoding": "UTF8",
            "sslmode": os.environ.get("POSTGRES_SSL_MODE", "prefer"),
            "application_name": "queueme",
        },
        "ATOMIC_REQUESTS": True,  # Wrap each request in a transaction for data consistency
        "CONN_HEALTH_CHECKS": True,  # Check connection health before use (Django 4.2+)
    }
}

# Database connection pooling (require django-db-connection-pool for production)
if os.environ.get("USE_CONNECTION_POOLING", "False").lower() == "true":
    try:
        # Dynamically import and configure connection pooling
        DATABASES["default"]["ENGINE"] = "dj_db_conn_pool.backends.postgresql"
        DATABASES["default"]["POOL_OPTIONS"] = {
            "POOL_SIZE": int(os.environ.get("DB_POOL_SIZE", 20)),
            "MAX_OVERFLOW": int(os.environ.get("DB_MAX_OVERFLOW", 15)),
            "RECYCLE": 300,  # Recycle connections after 5 minutes
            "TIMEOUT": 20,  # 20 seconds acquisition timeout
            "MAX_LIFETIME": 1800,  # 30 minutes maximum lifetime
            "POOL_PRE_PING": True,  # Enable connection health checks
        }
        print("Database connection pooling enabled.")
    except ImportError:
        print("Package django-db-connection-pool not installed. Connection pooling disabled.")
        # Fallback to standard PostgreSQL
        DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# SQLite fallback for development if needed
if os.environ.get("USE_SQLITE", "False").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.gis",
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
    "django_filters",
    "storages",
    "django_prometheus",
    # Core apps
    "core",
    "algorithms",
    "utils",  # Utility components including admin audit logs
    # Custom admin panel
    # Realtime gateway (avoid name clash with PyPI websockets)
    "websockets.apps.WebsocketsConfig",

    # Domain apps – explicit AppConfig paths
    "apps.authapp.apps.AuthAppConfig",
    "apps.rolesapp.apps.RolesappConfig",
    "apps.geoapp.apps.GeoAppConfig",
    "apps.companiesapp.apps.CompaniesappConfig",
    "apps.shopapp.apps.ShopAppConfig",
    "apps.employeeapp.apps.EmployeeAppConfig",
    "apps.specialistsapp.apps.SpecialistsAppConfig",
    "apps.categoriesapp.apps.CategoriesappConfig",
    "apps.serviceapp.apps.ServiceAppConfig",
    "apps.packageapp.apps.PackageAppConfig",
    "apps.bookingapp.apps.BookingAppConfig",
    "apps.queueapp.apps.QueueAppConfig",
    "apps.reviewapp.apps.ReviewAppConfig",
    "apps.customersapp.apps.CustomersConfig",
    "apps.discountapp.apps.DiscountappConfig",
    "apps.payment.apps.PaymentConfig",
    "apps.notificationsapp.apps.NotificationsAppConfig",
    "apps.chatapp.apps.ChatConfig",
    "apps.subscriptionapp.apps.SubscriptionAppConfig",
    "apps.followapp.apps.FollowappConfig",
    "apps.reelsapp.apps.ReelsAppConfig",
    "apps.storiesapp.apps.StoriesAppConfig",
    "apps.reportanalyticsapp.apps.ReportAnalyticsConfig",
    "apps.shopDashboardApp.apps.ShopDashboardAppConfig",
    "apps.marketingapp.apps.MarketingAppConfig",
    ]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "utils.admin.middleware.AdminAuditMiddleware",  # Admin audit logging - disabled temporarily
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "queueme.middleware.rate_limiting.RateLimitingMiddleware",
    "queueme.middleware.auth_middleware.JWTAuthMiddleware",
    "queueme.middleware.localization_middleware.LocalizationMiddleware",
    "queueme.middleware.performance_middleware.PerformanceMiddleware",
    "queueme.middleware.domain_routing.DomainRoutingMiddleware",
    "core.middleware.performance_middleware.PerformanceMonitoringMiddleware",  # Performance monitoring
    "django_prometheus.middleware.PrometheusAfterMiddleware",
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
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
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
        "apps.authapp.backends.QueueMeJWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "api.v1.throttling.UserBasicRateThrottle",
        "api.v1.throttling.AnonBasicRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon_basic": "30/minute",
        "user_basic": "100/minute",
        "anon_strict": "10/minute",
        "user_strict": "20/minute",
        "authentication": "5/minute",
        "payment": "10/minute",
        "search": "30/minute",
        "booking": "20/minute",
        "burst": "60/minute",
        "sustained": "1000/day",
    },
    "EXCEPTION_HANDLER": "api.v1.utils.custom_exception_handler",
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
# Celery - DISABLED TEMPORARILY
# ---------------------------------------------------------------------------
# CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/0")
# CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
# CELERY_TIMEZONE = "Asia/Riyadh"
# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60
# CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# CELERY_RESULT_EXTENDED = True

# Dummy Celery settings to prevent errors
DISABLE_CELERY = True
CELERY_ALWAYS_EAGER = True
CELERY_TASK_ALWAYS_EAGER = True


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
if all(env(v) for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME")):
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "me-south-1")
    AWS_S3_CUSTOM_DOMAIN = f"{env('AWS_STORAGE_BUCKET_NAME')}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
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
MOYASAR_API_KEY = env("MOYASAR_API_KEY", "")
MOYASAR_WEBHOOK_SECRET = env("MOYASAR_WEBHOOK_SECRET", "")

# Import Moyasar wallet configuration
try:
    from .moyasar import MOYASAR_ADS, MOYASAR_MER, MOYASAR_SUB, validate_moyasar_config

    # Log Moyasar wallet status
    if DEBUG:
        moyasar_status = validate_moyasar_config()
        has_issues = moyasar_status["missing_keys"] or moyasar_status["empty_keys"]
        if has_issues:
            print("⚠️ Moyasar wallet configuration issues detected:")
            if moyasar_status["missing_keys"]:
                print(f"  - Missing keys: {', '.join(moyasar_status['missing_keys'])}")
            if moyasar_status["empty_keys"]:
                print(f"  - Empty keys: {', '.join(moyasar_status['empty_keys'])}")

        print(
            "🔐 Moyasar wallets status: "
            + "Subscription: {} | Ads: {} | Merchant: {}".format(
                "✓" if moyasar_status["wallet_status"]["subscription"] else "✗",
                "✓" if moyasar_status["wallet_status"]["ads"] else "✗",
                "✓" if moyasar_status["wallet_status"]["merchant"] else "✗",
            )
        )
except ImportError:
    print("⚠️ Moyasar wallet configuration not found")
    MOYASAR_SUB = {}
    MOYASAR_ADS = {}
    MOYASAR_MER = {}

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", "")

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
# Security - Improved Default Values for Production
# ---------------------------------------------------------------------------
# Set secure defaults but allow overriding through environment variables
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", "1") == "1"  # Default to True in production
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", "1") == "1"  # Default to True in production
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", "1") == "1"  # Default to True in production
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))  # Default to 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"  # Default to True
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", "1") == "1"  # Default to True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"


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


# Rate limiting settings
RATE_LIMIT_DEFAULT_RATE = 100  # 100 requests
RATE_LIMIT_DEFAULT_PERIOD = 60  # per minute
RATE_LIMIT_API_RATE = 60  # 60 API requests
RATE_LIMIT_API_PERIOD = 60  # per minute
RATE_LIMIT_OTP_RATE = 5  # 5 OTP send requests
RATE_LIMIT_OTP_PERIOD = 300  # per 5 minutes (300 seconds)
RATE_LIMIT_OTP_LOCKOUT = 1800  # 30 minutes lockout after exceeding
RATE_LIMIT_OTP_VERIFY_RATE = 10  # 10 OTP verify attempts
RATE_LIMIT_OTP_VERIFY_PERIOD = 300  # per 5 minutes
RATE_LIMIT_OTP_VERIFY_LOCKOUT = 1800  # 30 minutes lockout after exceeding


print("🏗️  Settings loaded  |  DEBUG={}  |  DB={}".format(DEBUG, DATABASES["default"]["ENGINE"]))
print("🏗️  Installed apps: {}".format(", ".join(INSTALLED_APPS)))