"""
Authentication specific exceptions for better error handling.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class AuthBaseException(APIException):
    """Base class for all authentication exceptions."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Authentication error occurred.")
    default_code = "authentication_error"


class InvalidCredentialsError(AuthBaseException):
    """Exception raised when login credentials are invalid."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Invalid credentials provided.")
    default_code = "invalid_credentials"


class InvalidTokenError(AuthBaseException):
    """Exception raised when a token is invalid."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Invalid authentication token.")
    default_code = "invalid_token"


class TokenExpiredError(AuthBaseException):
    """Exception raised when a token has expired."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Authentication token has expired.")
    default_code = "token_expired"


class TokenBlacklistedError(AuthBaseException):
    """Exception raised when a token is blacklisted (revoked)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Authentication token has been revoked.")
    default_code = "token_blacklisted"


class TokenGenerationError(AuthBaseException):
    """Exception raised when token generation fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("Failed to generate authentication token.")
    default_code = "token_generation_error"


class OTPError(AuthBaseException):
    """Exception raised for OTP-related errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("OTP error occurred.")
    default_code = "otp_error"


class OTPExpiredError(OTPError):
    """Exception raised when an OTP has expired."""

    default_detail = _("OTP has expired.")
    default_code = "otp_expired"


class OTPInvalidError(OTPError):
    """Exception raised when an OTP is invalid."""

    default_detail = _("Invalid OTP.")
    default_code = "otp_invalid"


class OTPMaxAttemptsError(OTPError):
    """Exception raised when max OTP attempts are reached."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _("Maximum OTP verification attempts reached. Please request a new OTP.")
    default_code = "otp_max_attempts"


class UserInactiveError(AuthBaseException):
    """Exception raised when a user account is inactive."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("User account is inactive.")
    default_code = "user_inactive"


class PhoneNumberNotRegisteredError(AuthBaseException):
    """Exception raised when phone number is not registered."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _("Phone number is not registered.")
    default_code = "phone_not_registered"


class RateLimitExceededError(AuthBaseException):
    """Exception raised when rate limit is exceeded for auth operations."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _("Rate limit exceeded. Please try again later.")
    default_code = "rate_limit_exceeded"
