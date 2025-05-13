"""
Test settings for Queue Me project.

These settings override the base settings for test environments.
"""

from .base import *

# Use regular SQLite database for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

# Disable caching in tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Use console backend for emails in tests
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use dummy backend for SMS in tests
SMS_BACKEND = "utils.sms.backends.dummy.DummySMSBackend"

# Use in-memory channel layer for tests
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Use memory storage for files in tests
DEFAULT_FILE_STORAGE = "inmemorystorage.InMemoryStorage"

# Password hashers are slow; use fast ones for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Make tests faster by avoiding real translations
USE_I18N = False

# Run Celery tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable Moyasar real calls in tests
MOYASAR_TEST_MODE = True

# Disable throttling in tests
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

# Test-specific settings
QUEUEME = {
    "SKIP_OTP_VERIFICATION": True,  # Skip OTP verification in tests
    "DEMO_MODE": False,  # Disable demo mode in tests
    "PERFORMANCE_MONITORING": False,  # Disable performance monitoring
}

# Raise exceptions for template errors during tests
TEMPLATES[0]["OPTIONS"]["debug"] = True

# Disable logging during tests to speed them up
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}

print("🧪 Running in TEST mode")
