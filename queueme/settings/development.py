"""
Development settings for Queue Me project.

These settings override the base settings for local development environments.
"""

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-development-key-not-for-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Use PostgreSQL for development without PostGIS (simplifies setup)
# In your development.py settings file
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'queueme',
        'USER': 'queueme',
        'PASSWORD': 'Arisearise',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Use console backend for emails in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use console backend for SMS in development
SMS_BACKEND = "utils.sms.backends.console.ConsoleSMSBackend"

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

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
        INTERNAL_IPS = ["127.0.0.1"]
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