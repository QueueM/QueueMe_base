"""
Development settings for Queue Me project.

These settings override the base settings for local development environments.
"""

import os

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-development-key-not-for-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Use SQLite for development to simplify setup
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "queueme"),
        "USER": os.environ.get("POSTGRES_USER", "queueme"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "Arisearise"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 300,  # 5 minutes connection persistence
        "OPTIONS": {
            "connect_timeout": 5,
        },
        "ATOMIC_REQUESTS": True,  # Wrap each request in a transaction for data consistency
    }
}

# Enable connection pooling for improved performance
if "CONN_MAX_AGE" not in DATABASES["default"]:
    DATABASES["default"]["CONN_MAX_AGE"] = 300  # Keep connections alive for 5 minutes

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use console backend for SMS in development
SMS_BACKEND = "utils.sms.backends.console.ConsoleSMSBackend"

# ---------------------------------------------------------------------------
# CORS settings for development
# ---------------------------------------------------------------------------
# More restrictive CORS settings even for development
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Only allow credentials for our specific origins
CORS_ALLOW_CREDENTIALS = True

# Additional CORS security headers
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

# Disable SSL/HTTPS requirements
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use local storage for media files
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# Django Debug Toolbar
if DEBUG:
    try:
        import debug_toolbar

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1", "::1"]

        # Configure Debug Toolbar to only show on admin.queueme.net
        DEBUG_TOOLBAR_CONFIG = {
            "SHOW_TOOLBAR_CALLBACK": lambda request: (
                request.get_host().split(":")[0]
                in ("admin.queueme.net", "admin.localhost", "admin.127.0.0.1")
                or (
                    request.path.startswith("/admin/")
                    and request.META.get("REMOTE_ADDR") in ("127.0.0.1", "localhost", "::1")
                )
            ),
            "RENDER_PANELS": False,  # Don't automatically render panels to improve performance
            "ENABLE_STACKTRACES": True,
        }
    except ImportError:
        pass

# Set Celery to run tasks immediately in development
CELERY_TASK_ALWAYS_EAGER = True

# Cache settings for development
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Use in-memory channel layers for WebSockets in development
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Frontend URLs for development
FRONTEND_URL = "http://localhost:3000"
SHOP_PANEL_URL = "http://localhost:3001"
ADMIN_PANEL_URL = "http://localhost:3002"

# Logging - more verbose in development
LOGGING["loggers"]["django"]["level"] = "DEBUG"
LOGGING["loggers"]["queueme"]["level"] = "DEBUG"

# Development-specific settings for debugging
QUEUEME = {
    "SKIP_OTP_VERIFICATION": True,  # Skip actual OTP verification in development
    "DEMO_MODE": False,  # Enable demo mode with sample data
    "PERFORMANCE_MONITORING": True,  # Enable more detailed performance tracking
}

print("🚀 Running in DEVELOPMENT mode")
