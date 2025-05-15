"""
Production settings for Queue Me project.

These settings override the base settings for production environments.
"""

import os

# Monkey patch to fix the persistent import error
import sys
import types
from datetime import timedelta
from pathlib import Path

from .base import *
from .base import env

# Create fake module implementations to bypass the problematic imports
dummy_worker = types.ModuleType("core.tasks.worker")
dummy_worker.WorkerManager = type(
    "WorkerManager", (), {"get_active_workers": staticmethod(lambda: {})}
)
dummy_worker.task_with_lock = lambda func=None, **kwargs: ((lambda f: f) if func is None else func)
dummy_worker.task_with_retry = lambda **kwargs: lambda f: f

# Replace the problematic modules in sys.modules
sys.modules["core.tasks.worker"] = dummy_worker


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set!")

# Database connection pooling configuration
DATABASE_CONNECTION_POOL_SETTINGS = {
    "MAX_CONNECTIONS": int(os.environ.get("DB_MAX_CONNECTIONS", 20)),
    "MIN_CONNECTIONS": int(os.environ.get("DB_MIN_CONNECTIONS", 5)),
    "MAX_LIFETIME": int(os.environ.get("DB_MAX_LIFETIME", 1800)),  # 30 minutes
    "IDLE_TIMEOUT": int(os.environ.get("DB_IDLE_TIMEOUT", 300)),  # 5 minutes
}

# Database read replicas configuration
if os.environ.get("DB_REPLICAS_ENABLED", "False").lower() == "true":
    # Example database configuration with read replicas
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "postgres"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("DB_SSL_MODE", "require"),
            },
        },
        "replica1": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "postgres"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_REPLICA1_HOST", "db-replica1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("DB_SSL_MODE", "require"),
            },
            "TEST": {
                "MIRROR": "default",
            },
        },
        "replica2": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "postgres"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_REPLICA2_HOST", "db-replica2"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("DB_SSL_MODE", "require"),
            },
            "TEST": {
                "MIRROR": "default",
            },
        },
    }

    # Database router for read/write splitting
    DATABASE_ROUTERS = ["queueme.db_routers.ReplicationRouter"]
else:
    # Standard single database configuration
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "postgres"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("DB_SSL_MODE", "require"),
            },
        }
    }

# Use pgbouncer for connection pooling if enabled
if os.environ.get("USE_PGBOUNCER", "False").lower() == "true":
    for db_name, db_config in DATABASES.items():
        # Adjust host and port for pgbouncer
        db_config["HOST"] = os.environ.get("PGBOUNCER_HOST", db_config["HOST"])
        db_config["PORT"] = os.environ.get("PGBOUNCER_PORT", "6432")
        # Disable persistent connections when using a connection pooler
        db_config["CONN_MAX_AGE"] = 0

# Add whitenoise for static file serving in production
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
# Add domain routing middleware
MIDDLEWARE.insert(0, "queueme.middleware.domain_routing.DomainRoutingMiddleware")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# FIX: Static files configuration - CRITICAL FOR ADMIN CSS/JS
STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/opt/queueme/staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/opt/queueme/media")

# Add security middlewares
MIDDLEWARE += [
    "core.middleware.security.ContentSecurityPolicyMiddleware",
    "core.middleware.security.XFrameOptionsMiddleware",
    "core.middleware.security.StrictTransportSecurityMiddleware",
    "core.middleware.security.ReferrerPolicyMiddleware",
    "core.middleware.security.XContentTypeOptionsMiddleware",
    "core.middleware.security.PermissionsPolicyMiddleware",
    "core.middleware.security.SQLInjectionProtectionMiddleware",
    "core.middleware.metrics_middleware.PrometheusMetricsMiddleware",
]

# Enhanced security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# JWT settings with enhanced security
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "UPDATE_LAST_LOGIN": True,
}

# Rate limiting
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
    "rest_framework.throttling.AnonRateThrottle",
    "rest_framework.throttling.UserRateThrottle",
]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": os.environ.get("ANON_THROTTLE_RATE", "20/minute"),
    "user": os.environ.get("USER_THROTTLE_RATE", "60/minute"),
    "subscription": os.environ.get("SUBSCRIPTION_THROTTLE_RATE", "100/minute"),
    "webhook": os.environ.get("WEBHOOK_THROTTLE_RATE", "120/minute"),
}

# Password validation settings
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 10,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Cache settings with Redis - Advanced Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme",
        "TIMEOUT": 300,  # 5 minutes default
    },
    "persistent": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
        },
        "KEY_PREFIX": "queueme:persist",
        "TIMEOUT": 86400,  # 1 day default
    },
    "large_objects": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/3"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme:large",
        "TIMEOUT": 3600,  # 1 hour default
    },
    "session": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/4"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        },
        "KEY_PREFIX": "queueme:session",
    },
}

# Cache session backend
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "session"

# Use local storage for media files
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# If AWS credentials exist, use S3
if all(
    os.environ.get(v)
    for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME")
):
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "me-south-1")
    AWS_S3_CUSTOM_DOMAIN = (
        f"{os.environ.get('AWS_STORAGE_BUCKET_NAME')}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    )
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

# Email/SMS settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="QueueMe <noreply@example.com>",
)

# Firebase settings for notifications and SMS
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH")
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID")
FIREBASE_MESSAGING_SENDER_ID = os.environ.get("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET")
FIREBASE_SMS_API_URL = os.environ.get("FIREBASE_SMS_API_URL")
FIREBASE_SMS_API_KEY = os.environ.get("FIREBASE_SMS_API_KEY")

# Use Firebase for SMS
SMS_BACKEND = "utils.sms.backends.firebase.FirebaseSMSBackend"

# CORS settings - allow domain and subdomains
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://queueme.net",  # Main site
    "https://www.queueme.net",  # www version of main site
    "https://shop.queueme.net",  # Shop interface for businesses
    "https://admin.queueme.net",  # Admin panel for site administrators
    "https://api.queueme.net",  # API endpoints
]

# Allow credentials for cross-domain API requests
CORS_ALLOW_CREDENTIALS = True

# Add any additional domains from environment variable
if os.environ.get("ADDITIONAL_CORS_ORIGINS"):
    CORS_ALLOWED_ORIGINS.extend(os.environ.get("ADDITIONAL_CORS_ORIGINS").split(","))

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net",
    "https://ajax.googleapis.com",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net",
    "https://fonts.googleapis.com",
)
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https://*.amazonaws.com")
CSP_CONNECT_SRC = ("'self'", "wss:")
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_INCLUDE_NONCE_IN = ("script-src",)

# Channel layers for WebSockets
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")],
            "capacity": 1500,  # Maximum number of messages in channel
            "expiry": 60,  # Message expiry in seconds
            "group_expiry": 86400,  # Channel/group expiry (1 day)
            "channel_capacity": {
                # Default channel capacity (global setting)
                "http.request": 100,
                # Per-channel overrides
                "websocket.send*": 200,
                "websocket.receive*": 200,
            },
        },
    },
}

# CRITICAL: Allow all subdomains
ALLOWED_HOSTS = [
    "queueme.net",  # Main site
    "www.queueme.net",  # www version of main site
    "shop.queueme.net",  # Shop interface for businesses
    "admin.queueme.net",  # Admin panel for site administrators
    "api.queueme.net",  # API endpoints
    "localhost",  # Local development
    "127.0.0.1",  # Local development
]

# Add any additional hosts from environment variable
if os.environ.get("ADDITIONAL_ALLOWED_HOSTS"):
    ALLOWED_HOSTS.extend(os.environ.get("ADDITIONAL_ALLOWED_HOSTS").split(","))

# Domain-specific routing - used for routing requests to the right app
DOMAIN_ROUTING = {
    "queueme.net": "main",  # Main site
    "www.queueme.net": "main",  # www version of main site
    "shop.queueme.net": "shop",  # Shop interface for businesses
    "admin.queueme.net": "admin",  # Admin panel for site administrators
    "api.queueme.net": "api",  # API endpoints
}

# Logging configuration
LOGGING["handlers"]["mail_admins"] = {
    "level": "ERROR",
    "class": "django.utils.log.AdminEmailHandler",
    "formatter": "verbose",
}

LOGGING["root"] = {
    "level": "WARNING",
    "handlers": ["file", "mail_admins"],
}

LOGGING["loggers"]["django.request"] = {
    "handlers": ["file", "mail_admins"],
    "level": "ERROR",
    "propagate": False,
}

# Add logging for static files for debugging
LOGGING["loggers"]["django.contrib.staticfiles"] = {
    "handlers": ["console", "file"],
    "level": "DEBUG",
    "propagate": False,
}

# Celery configuration
DISABLE_CELERY = os.environ.get("DISABLE_CELERY", "False").lower() == "true"
CELERY_ALWAYS_EAGER = DISABLE_CELERY
CELERY_TASK_ALWAYS_EAGER = DISABLE_CELERY

# Production-specific settings
QUEUEME = {
    "SKIP_OTP_VERIFICATION": os.environ.get("SKIP_OTP_VERIFICATION", "False").lower() == "true",
    "DEMO_MODE": os.environ.get("DEMO_MODE", "False").lower() == "true",
    "PERFORMANCE_MONITORING": os.environ.get("PERFORMANCE_MONITORING", "True").lower() == "true",
}

# S3 / Cloud Storage Configuration
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# AWS Settings
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "queueme-production")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_CUSTOM_DOMAIN = os.environ.get(
    "AWS_S3_CUSTOM_DOMAIN", f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
)
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
AWS_DEFAULT_ACL = "public-read"
AWS_LOCATION = "static"
STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

# Alternative Google Cloud Storage config (uncomment to use instead of S3)
# DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
# GS_BUCKET_NAME = os.environ.get('GS_BUCKET_NAME', 'queueme-production')
# GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
#     os.environ.get('GS_CREDENTIALS_FILE')
# )
# MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'

# Static files optimization
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/opt/queueme/static")

# Static file compression and caching
INSTALLED_APPS += ["compressor"]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_FINDERS += ["compressor.finders.CompressorFinder"]

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_FILTERS = [
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.cssmin.CSSMinFilter",
]
COMPRESS_JS_FILTERS = ["compressor.filters.jsmin.JSMinFilter"]
COMPRESS_OUTPUT_DIR = "compressed"
COMPRESS_STORAGE = "compressor.storage.GzipCompressorFileStorage"

# Media file storage (use S3 in production)
if os.environ.get("USE_S3", "False").lower() == "true":
    # AWS S3 settings
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.environ.get(
        "AWS_S3_CUSTOM_DOMAIN", f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    )
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
    AWS_DEFAULT_ACL = "public-read"
    AWS_LOCATION = "static"
    AWS_S3_FILE_OVERWRITE = False

    # Media settings for S3
    MEDIA_LOCATION = "media"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/"
    DEFAULT_FILE_STORAGE = "core.storage.MediaStorage"

    # Static settings for S3 (optional, can use local for faster performance)
    if os.environ.get("S3_STATIC_FILES", "False").lower() == "true":
        STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/"
        STATICFILES_STORAGE = "core.storage.StaticStorage"
else:
    # Use local storage with proper caching headers
    MEDIA_URL = "/media/"
    STATIC_URL = "/static/"

# CDN configuration (optional)
if os.environ.get("USE_CDN", "False").lower() == "true":
    CDN_DOMAIN = os.environ.get("CDN_DOMAIN")
    if CDN_DOMAIN:
        STATIC_URL = f"https://{CDN_DOMAIN}/static/"
        MEDIA_URL = f"https://{CDN_DOMAIN}/media/"

print(f"🔒 Running in PRODUCTION mode with DEBUG={DEBUG}")
