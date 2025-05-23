"""
Constants for the authentication application.
These values can be overridden in settings.
"""

from django.conf import settings

# OTP validity duration in minutes
OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)

# Maximum attempts to verify OTP
MAX_OTP_VERIFICATION_ATTEMPTS = getattr(settings, "MAX_OTP_VERIFICATION_ATTEMPTS", 3)

# Number of OTPs allowed in an hour (for rate limiting)
MAX_OTP_REQUESTS_PER_HOUR = getattr(settings, "MAX_OTP_REQUESTS_PER_HOUR", 5)

# Number of OTPs allowed in a day (for rate limiting)
MAX_OTP_REQUESTS_PER_DAY = getattr(settings, "MAX_OTP_REQUESTS_PER_DAY", 15)

# Number of OTPs allowed in a week (for rate limiting)
MAX_OTP_REQUESTS_PER_WEEK = getattr(settings, "MAX_OTP_REQUESTS_PER_WEEK", 50)

# OTP length
OTP_LENGTH = getattr(settings, "OTP_LENGTH", 6)

# JWT access token lifetime in minutes
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = getattr(
    settings, "JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60
)

# JWT refresh token lifetime in days
JWT_REFRESH_TOKEN_LIFETIME_DAYS = getattr(
    settings, "JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7
)

# Account security settings
ACCOUNT_LOCK_DURATION = getattr(
    settings, "ACCOUNT_LOCK_DURATION", 3600
)  # 1 hour in seconds
MAX_LOGIN_ATTEMPTS = getattr(
    settings, "MAX_LOGIN_ATTEMPTS", 5
)  # Maximum failed login attempts
MAX_FAILED_LOGIN_ATTEMPTS = getattr(
    settings, "MAX_FAILED_LOGIN_ATTEMPTS", 5
)  # Alternative name for consistency
SECURITY_LOCKOUT_ENABLED = getattr(settings, "SECURITY_LOCKOUT_ENABLED", True)
PASSWORD_MIN_LENGTH = getattr(settings, "PASSWORD_MIN_LENGTH", 8)
PASSWORD_MAX_LENGTH = getattr(settings, "PASSWORD_MAX_LENGTH", 128)
PASSWORD_HISTORY_COUNT = getattr(settings, "PASSWORD_HISTORY_COUNT", 5)

# Session settings
SESSION_TIMEOUT = getattr(settings, "SESSION_TIMEOUT", 86400)  # 24 hours in seconds
DEVICE_SESSION_LIMIT = getattr(settings, "DEVICE_SESSION_LIMIT", 5)

# Rate limiting
API_RATE_LIMIT_PER_MINUTE = getattr(settings, "API_RATE_LIMIT_PER_MINUTE", 60)
OTP_RATE_LIMIT_PER_HOUR = getattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 10)

# Rate limiting periods (in seconds)
RATE_LIMIT_PERIODS = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
}

# User types
USER_TYPE_CUSTOMER = "customer"
USER_TYPE_EMPLOYEE = "employee"
USER_TYPE_ADMIN = "admin"
USER_TYPE_SHOP_OWNER = "shop_owner"
USER_TYPE_SPECIALIST = "specialist"

USER_TYPE_CHOICES = (
    (USER_TYPE_CUSTOMER, "Customer"),
    (USER_TYPE_EMPLOYEE, "Employee"),
    (USER_TYPE_ADMIN, "Admin"),
    (USER_TYPE_SHOP_OWNER, "Shop Owner"),
    (USER_TYPE_SPECIALIST, "Specialist"),
)

# Verification statuses
VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_FAILED = "failed"

# Language preferences
LANGUAGE_ENGLISH = "en"
LANGUAGE_ARABIC = "ar"
LANGUAGE_ENGLISH_US = "en-us"
LANGUAGE_ARABIC_SA = "ar-sa"

# Device types
DEVICE_TYPE_IOS = "ios"
DEVICE_TYPE_ANDROID = "android"
DEVICE_TYPE_WEB = "web"
