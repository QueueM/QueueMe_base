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

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Use PostgreSQL for development with proper host settings
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
            "sslmode": os.environ.get("POSTGRES_SSL_MODE", "disable"),
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

# Disable SSL/HTTPS requirements in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Use local storage for media files
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# Django Debug Toolbar - Completely fixed configuration
if DEBUG:
    try:
        import debug_toolbar
        
        # Add the app to INSTALLED_APPS if not already there
        if 'debug_toolbar' not in INSTALLED_APPS:
            INSTALLED_APPS.append('debug_toolbar')
        
        # Add middleware if not already present
        if 'debug_toolbar.middleware.DebugToolbarMiddleware' not in MIDDLEWARE:
            MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        
        # Set internal IPs
        INTERNAL_IPS = ["127.0.0.1", "::1", "localhost"]
        
        # Comprehensive Debug Toolbar configuration
        DEBUG_TOOLBAR_CONFIG = {
            # Disable problematic panels
            'DISABLE_PANELS': [
                'debug_toolbar.panels.history.HistoryPanel',  # Disable history panel that causes 404s
                'debug_toolbar.panels.redirects.RedirectsPanel',  # Optional: disable if causing issues
            ],
            # Only show toolbar in admin or for specific hosts
            'SHOW_TOOLBAR_CALLBACK': lambda request: (
                request.get_host().split(":")[0]
                in ("admin.queueme.net", "admin.localhost", "admin.127.0.0.1", "127.0.0.1", "localhost")
                or (
                    request.path.startswith("/admin/")
                    and request.META.get("REMOTE_ADDR") in ["127.0.0.1", "::1", "localhost"]
                )
            ),
            'RENDER_PANELS': False,  # Don't auto-render panels for performance
            'ENABLE_STACKTRACES': True,
            'RESULTS_CACHE_SIZE': 10,  # Limit history size
            'SHOW_COLLAPSED': True,  # Start with toolbar collapsed
            'SQL_WARNING_THRESHOLD': 500,  # ms, threshold for highlighting slow queries
        }
        
        # Use minimal panels to avoid issues
        DEBUG_TOOLBAR_PANELS = [
            'debug_toolbar.panels.versions.VersionsPanel',
            'debug_toolbar.panels.timer.TimerPanel',
            'debug_toolbar.panels.settings.SettingsPanel',
            'debug_toolbar.panels.headers.HeadersPanel',
            'debug_toolbar.panels.request.RequestPanel',
            'debug_toolbar.panels.sql.SQLPanel',
            'debug_toolbar.panels.staticfiles.StaticFilesPanel',
            'debug_toolbar.panels.templates.TemplatesPanel',
            'debug_toolbar.panels.cache.CachePanel',
            'debug_toolbar.panels.signals.SignalsPanel',
            'debug_toolbar.panels.logging.LoggingPanel',
            # Explicitly exclude problematic panels
            # 'debug_toolbar.panels.history.HistoryPanel',
            # 'debug_toolbar.panels.redirects.RedirectsPanel',
        ]
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

# Add debugging for Django's database operations
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": "DEBUG" if DEBUG else "INFO",
    "propagate": False,
}

# Development-specific settings for debugging
QUEUEME = {
    "SKIP_OTP_VERIFICATION": True,  # Skip actual OTP verification in development
    "DEMO_MODE": False,  # Enable demo mode with sample data
    "PERFORMANCE_MONITORING": True,  # Enable more detailed performance tracking
}

print("🚀 Running in DEVELOPMENT mode")