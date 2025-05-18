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
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = getattr(settings, "JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60)

# JWT refresh token lifetime in days
JWT_REFRESH_TOKEN_LIFETIME_DAYS = getattr(settings, "JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7)

# User types
USER_TYPE_CUSTOMER = "customer"
USER_TYPE_EMPLOYEE = "employee"
USER_TYPE_ADMIN = "admin"

USER_TYPE_CHOICES = (
    (USER_TYPE_CUSTOMER, "Customer"),
    (USER_TYPE_EMPLOYEE, "Employee"),
    (USER_TYPE_ADMIN, "Admin"),
)
