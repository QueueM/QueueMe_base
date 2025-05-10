"""
Production settings for Queue Me project.

These settings override the base settings for production environments.
"""

from .base import *

# SECURITY WARNING: force DEBUG to be false in production regardless of .env
# This is critical for security!
os.environ["DEBUG"] = "False"
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set!")

# Use PostGIS in production
# Set the engine at the database level to override settings from dj_database_url
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# Add production-specific database options
DATABASES["default"]["CONN_MAX_AGE"] = 600  # Keep connections alive for 10 minutes
DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 10,  # 10 seconds connection timeout
}

# Enable SSL and security features
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cache settings for production
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 5,  # seconds
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "queueme",
        "TIMEOUT": 300,  # 5 minutes default timeout
    }
}

# Cache session backend
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Use S3 for media storage
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Enable SMTP email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Enable real SMS backend for production
SMS_BACKEND = "utils.sms.backends.twilio.TwilioBackend"

# CORS settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://queueme.net",
    "https://www.queueme.net",
    "https://shop.queueme.net",
    "https://admin.queueme.net",
]

# Add CSP (Content Security Policy)
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", f"https://{AWS_S3_CUSTOM_DOMAIN}")
CSP_CONNECT_SRC = ("'self'",)

# Optimized Channel Layers for production
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (
                    os.environ.get("REDIS_HOST", "localhost"),
                    int(os.environ.get("REDIS_PORT", 6379)),
                )
            ],
            "capacity": 1500,  # Default channel layer capacity
            "expiry": 10,  # Message expiry time in seconds
        },
    },
}

# REST Framework throttle rates for production
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "50/hour",
    "user": "500/hour",
    "otp": "5/hour",
}

# Set allowed hosts from environment (comma-separated)
ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "queueme.net,www.queueme.net,shop.queueme.net,admin.queueme.net"
).split(",")

# Close old connections before each request
CONN_MAX_AGE = 60

# Configure additional logging for production
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
    "handlers": ["mail_admins"],
    "level": "ERROR",
    "propagate": False,
}

# Production-specific settings
QUEUEME = {
    "SKIP_OTP_VERIFICATION": False,  # Always verify OTPs in production
    "DEMO_MODE": False,  # Disable demo mode in production
    "PERFORMANCE_MONITORING": True,  # Enable performance monitoring
}

print("🔒 Running in PRODUCTION mode")
