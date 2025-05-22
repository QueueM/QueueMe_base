"""
Production settings for Queue Me project.

These settings override the base settings for production environments.
"""

import os
import sys
import types
from datetime import timedelta

from .base import *
from .base import env

# Monkey patch to fix persistent import errors in production (Celery worker)
dummy_worker = types.ModuleType("core.tasks.worker")
dummy_worker.WorkerManager = type(
    "WorkerManager", (), {"get_active_workers": staticmethod(lambda: {})}
)
dummy_worker.task_with_lock = lambda func=None, **kwargs: (
    (lambda f: f) if func is None else func
)
dummy_worker.task_with_retry = lambda **kwargs: lambda f: f
sys.modules["core.tasks.worker"] = dummy_worker

# =============================== STATIC FILES ===============================
STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/opt/queueme/static")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
# ============================================================================

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set!")

DATABASE_CONNECTION_POOL_SETTINGS = {
    "MAX_CONNECTIONS": int(os.environ.get("DB_MAX_CONNECTIONS", 20)),
    "MIN_CONNECTIONS": int(os.environ.get("DB_MIN_CONNECTIONS", 5)),
    "MAX_LIFETIME": int(os.environ.get("DB_MAX_LIFETIME", 1800)),
    "IDLE_TIMEOUT": int(os.environ.get("DB_IDLE_TIMEOUT", 300)),
}

# ================== SWAGGER SETTINGS FOR PRODUCTION ========================
SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "queueme.urls.api_info",
    "USE_SESSION_AUTH": False,
    "SHOW_REQUEST_HEADERS": True,
    "VALIDATOR_URL": None,
    "DEFAULT_MODEL_RENDERING": "example",
    "DOC_EXPANSION": "none",
    "PERSIST_AUTH": True,
    "REFETCH_SCHEMA_WITH_AUTH": True,
    "SHOW_EXTENSIONS": True,
    "DEBUG": True,  # Set to False for clean prod docs if desired
    # CRITICAL: robust deduplication + error-proof schema
    "FUNCTION_TO_APPLY_BEFORE_SWAGGER_SCHEMA_VALIDATION": "api.documentation.utils.dedupe_operation_params",
    "DEFAULT_AUTO_SCHEMA_CLASS": "api.documentation.yasg_patch.SafeSwaggerSchema",
}
# ============================================================================

if os.environ.get("DB_REPLICAS_ENABLED", "False").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "queueme"),
            "USER": os.environ.get("POSTGRES_USER", "queueme"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "Arisearise"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("POSTGRES_SSL_MODE", "prefer"),
            },
        },
        "replica1": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "queueme"),
            "USER": os.environ.get("POSTGRES_USER", "queueme"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "Arisearise"),
            "HOST": os.environ.get("POSTGRES_REPLICA1_HOST", "db-replica1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("POSTGRES_SSL_MODE", "prefer"),
            },
            "TEST": {"MIRROR": "default"},
        },
    }
    DATABASE_ROUTERS = ["queueme.db_routers.ReplicationRouter"]
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ.get("POSTGRES_DB", "queueme"),
            "USER": os.environ.get("POSTGRES_USER", "queueme"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "Arisearise"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": DATABASE_CONNECTION_POOL_SETTINGS["MAX_LIFETIME"],
            "OPTIONS": {
                "connect_timeout": 5,
                "client_encoding": "UTF8",
                "sslmode": os.environ.get("POSTGRES_SSL_MODE", "prefer"),
            },
        }
    }

# PGBouncer: Connection pooling support
if os.environ.get("USE_PGBOUNCER", "False").lower() == "true":
    for db_name, db_config in DATABASES.items():
        db_config["HOST"] = os.environ.get("PGBOUNCER_HOST", db_config["HOST"])
        db_config["PORT"] = os.environ.get("PGBOUNCER_PORT", "6432")
        db_config["CONN_MAX_AGE"] = 0

# Remove whitenoise if present (for S3/CDN)
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m.lower()]
MIDDLEWARE.insert(0, "queueme.middleware.domain_routing.DomainRoutingMiddleware")

# Media configuration
MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/opt/queueme/media")
if os.environ.get("USE_S3_MEDIA", "False").lower() == "true" and all(
    os.environ.get(v)
    for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME")
):
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "me-south-1")
    AWS_S3_CUSTOM_DOMAIN = f"{os.environ.get('AWS_STORAGE_BUCKET_NAME')}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
else:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    MEDIA_URL = "/media/"

# Debug toolbar for debug only
if DEBUG and os.environ.get("ENABLE_DEBUG_TOOLBAR", "False").lower() == "true":
    try:
        pass

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1", "::1", "localhost"]
        DEBUG_TOOLBAR_CONFIG = {
            "DISABLE_PANELS": [
                "debug_toolbar.panels.history.HistoryPanel",
                "debug_toolbar.panels.redirects.RedirectsPanel",
            ],
            "SHOW_TOOLBAR_CALLBACK": lambda request: (
                request.user.is_superuser
                and request.META.get("REMOTE_ADDR") in INTERNAL_IPS
            ),
            "RENDER_PANELS": False,
            "ENABLE_STACKTRACES": False,
            "SHOW_COLLAPSED": True,
        }
    except ImportError:
        pass
else:
    INSTALLED_APPS = [
        app
        for app in INSTALLED_APPS
        if not (isinstance(app, str) and "debug_toolbar" in app)
    ]
    MIDDLEWARE = [
        mw for mw in MIDDLEWARE if not (isinstance(mw, str) and "debug_toolbar" in mw)
    ]

# Security middlewares
security_middlewares = [
    "core.middleware.security.ContentSecurityPolicyMiddleware",
    "core.middleware.security.XFrameOptionsMiddleware",
    "core.middleware.security.StrictTransportSecurityMiddleware",
    "core.middleware.security.ReferrerPolicyMiddleware",
    "core.middleware.security.XContentTypeOptionsMiddleware",
    "core.middleware.security.PermissionsPolicyMiddleware",
    "core.middleware.security.SQLInjectionProtectionMiddleware",
]
try:
    pass

    try:
        pass

        security_middlewares.append(
            "core.middleware.metrics_middleware.PrometheusMetricsMiddleware"
        )
    except ImportError:
        print("⚠️ PrometheusMetricsMiddleware not loaded - API_REQUESTS missing")
except ImportError:
    print("⚠️ PrometheusMetricsMiddleware not loaded - metrics module missing")
MIDDLEWARE += security_middlewares

SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"
)
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "1") == "1"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "1") == "1"
X_FRAME_OPTIONS = "DENY"

# JWT settings (override any base.py values as needed)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_DAYS", "7"))
    ),
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

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme",
        "TIMEOUT": 300,
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
        "TIMEOUT": 86400,
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
        "TIMEOUT": 3600,
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

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "session"

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

FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH")
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID")
FIREBASE_MESSAGING_SENDER_ID = os.environ.get("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET")
FIREBASE_SMS_API_URL = os.environ.get("FIREBASE_SMS_API_URL")
FIREBASE_SMS_API_KEY = os.environ.get("FIREBASE_SMS_API_KEY")

SMS_BACKEND = "utils.sms.backends.firebase.FirebaseSMSBackend"

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://queueme.net",
    "https://www.queueme.net",
    "https://shop.queueme.net",
    "https://admin.queueme.net",
    "https://api.queueme.net",
]
if os.environ.get("ADDITIONAL_CORS_ORIGINS"):
    CORS_ALLOWED_ORIGINS.extend(os.environ.get("ADDITIONAL_CORS_ORIGINS").split(","))
CORS_ALLOW_CREDENTIALS = True

# Content Security Policy (CSP)
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

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")],
            "capacity": 1500,
            "expiry": 60,
            "group_expiry": 86400,
            "channel_capacity": {
                "http.request": 100,
                "websocket.send*": 200,
                "websocket.receive*": 200,
            },
        },
    },
}

ALLOWED_HOSTS = [
    "queueme.net",
    "www.queueme.net",
    "shop.queueme.net",
    "admin.queueme.net",
    "api.queueme.net",
    "localhost",
    "127.0.0.1",
    "148.72.244.135",
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if os.environ.get("ADDITIONAL_ALLOWED_HOSTS"):
    ALLOWED_HOSTS.extend(os.environ.get("ADDITIONAL_ALLOWED_HOSTS").split(","))

DOMAIN_ROUTING = {
    "queueme.net": "main",
    "www.queueme.net": "main",
    "shop.queueme.net": "shop",
    "admin.queueme.net": "admin",
    "api.queueme.net": "api",
}

# Logging adjustments
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
LOGGING["loggers"]["django.contrib.staticfiles"] = {
    "handlers": ["console", "file"],
    "level": "DEBUG",
    "propagate": False,
}

# Celery settings for prod: disable if needed
DISABLE_CELERY = os.environ.get("DISABLE_CELERY", "False").lower() == "true"
CELERY_ALWAYS_EAGER = DISABLE_CELERY
CELERY_TASK_ALWAYS_EAGER = DISABLE_CELERY

QUEUEME = {
    "SKIP_OTP_VERIFICATION": os.environ.get("SKIP_OTP_VERIFICATION", "False").lower()
    == "true",
    "DEMO_MODE": os.environ.get("DEMO_MODE", "False").lower() == "true",
    "PERFORMANCE_MONITORING": os.environ.get("PERFORMANCE_MONITORING", "True").lower()
    == "true",
}

# CDN configuration (optional)
if os.environ.get("USE_CDN", "False").lower() == "true":
    CDN_DOMAIN = os.environ.get("CDN_DOMAIN")
    if CDN_DOMAIN:
        STATIC_URL = f"https://{CDN_DOMAIN}/static/"
        MEDIA_URL = f"https://{CDN_DOMAIN}/media/"

print(f"🔒 Running in PRODUCTION mode with DEBUG={DEBUG}")

# END OF FILE
