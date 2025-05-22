"""
Development settings for Queue Me project.

These settings override the base settings for local development environments.
"""

import os

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", "django-insecure-development-key-not-for-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG", "True") == "True"

# Allow all hosts in development (for convenience)
ALLOWED_HOSTS = ["*", "148.72.244.135"]

# PostgreSQL local dev config (adjust as needed)
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "queueme"),
        "USER": os.environ.get("POSTGRES_USER", "queueme"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "Arisearise"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 300,
        "OPTIONS": {
            "connect_timeout": 5,
            "sslmode": os.environ.get("POSTGRES_SSL_MODE", "disable"),
        },
        "ATOMIC_REQUESTS": True,
    }
}

# ---------------------------------------------------------------------------
# Swagger settings: robust dedupe + SafeSwaggerSchema for error tolerance
# ---------------------------------------------------------------------------
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
    "DEBUG": True,
    # CRITICAL: dedupe + error-proof docs
    "FUNCTION_TO_APPLY_BEFORE_SWAGGER_SCHEMA_VALIDATION": "api.documentation.utils.dedupe_operation_params",
    "DEFAULT_AUTO_SCHEMA_CLASS": "api.documentation.yasg_patch.SafeSwaggerSchema",
}

# Enable connection pooling for improved performance (optional, usually production)
if "CONN_MAX_AGE" not in DATABASES["default"]:
    DATABASES["default"]["CONN_MAX_AGE"] = 300

# Email and SMS (console backend in dev)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SMS_BACKEND = "utils.sms.backends.console.ConsoleSMSBackend"

# Static & media config (local storage only in dev)
STATIC_URL = "/static/"
STATIC_ROOT = "/opt/queueme/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# WhiteNoise for local static serving (always in dev)
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m.lower()]
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# CORS (restrict as much as you like in dev)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Security in development (no SSL, no secure cookies, no HSTS)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Debug Toolbar (full setup for local debugging)
if DEBUG:
    try:
        pass

        if "debug_toolbar" not in INSTALLED_APPS:
            INSTALLED_APPS.append("debug_toolbar")
        if "debug_toolbar.middleware.DebugToolbarMiddleware" not in MIDDLEWARE:
            MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1", "::1", "localhost"]
        DEBUG_TOOLBAR_CONFIG = {
            "DISABLE_PANELS": [
                "debug_toolbar.panels.history.HistoryPanel",
                "debug_toolbar.panels.redirects.RedirectsPanel",
            ],
            "SHOW_TOOLBAR_CALLBACK": lambda request: (
                request.get_host().split(":")[0]
                in (
                    "admin.queueme.net",
                    "admin.localhost",
                    "admin.127.0.0.1",
                    "127.0.0.1",
                    "localhost",
                )
                or (
                    (
                        request.path.startswith("/admin/")
                        or request.path.startswith("/django-admin/")
                    )
                    and request.META.get("REMOTE_ADDR")
                    in ["127.0.0.1", "::1", "localhost"]
                )
            ),
            "RENDER_PANELS": False,
            "ENABLE_STACKTRACES": True,
            "RESULTS_CACHE_SIZE": 10,
            "SHOW_COLLAPSED": True,
            "SQL_WARNING_THRESHOLD": 500,
        }
        DEBUG_TOOLBAR_PANELS = [
            "debug_toolbar.panels.versions.VersionsPanel",
            "debug_toolbar.panels.timer.TimerPanel",
            "debug_toolbar.panels.settings.SettingsPanel",
            "debug_toolbar.panels.headers.HeadersPanel",
            "debug_toolbar.panels.request.RequestPanel",
            "debug_toolbar.panels.sql.SQLPanel",
            "debug_toolbar.panels.staticfiles.StaticFilesPanel",
            "debug_toolbar.panels.templates.TemplatesPanel",
            "debug_toolbar.panels.cache.CachePanel",
            "debug_toolbar.panels.signals.SignalsPanel",
            "debug_toolbar.panels.logging.LoggingPanel",
        ]
    except ImportError:
        pass

# Celery: always run tasks immediately in dev
CELERY_TASK_ALWAYS_EAGER = True

# Dev cache: local memory
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Channels: in-memory for dev, Redis not required
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# URLs for all panels for local dev (match your local frontend)
FRONTEND_URL = "http://localhost:3000"
SHOP_PANEL_URL = "http://localhost:3001"
ADMIN_PANEL_URL = "http://localhost:3002"

# Domain routing for dev environment
DOMAIN_ROUTING = {
    "queueme.net": "main",
    "www.queueme.net": "main",
    "shop.queueme.net": "shop",
    "admin.queueme.net": "admin",
    "api.queueme.net": "api",
    "localhost": "main",
    "127.0.0.1": "main",
}

# Logging: verbose in dev, debug everything
LOGGING["loggers"]["django"]["level"] = "DEBUG"
LOGGING["loggers"]["queueme"]["level"] = "DEBUG"
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": "DEBUG" if DEBUG else "INFO",
    "propagate": False,
}
LOGGING["loggers"]["django.contrib.staticfiles"] = {
    "handlers": ["console"],
    "level": "DEBUG",
    "propagate": False,
}

# Dev-specific toggles
QUEUEME = {
    "SKIP_OTP_VERIFICATION": True,
    "DEMO_MODE": False,
    "PERFORMANCE_MONITORING": True,
}

print("�� Running in DEVELOPMENT mode")
