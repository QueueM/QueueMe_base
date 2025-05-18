"""
Custom exceptions for Queue Me platform.

This module defines custom exceptions for use throughout the platform,
enabling consistent error handling patterns.
"""

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import status


class QueueMeError(Exception):
    """
    Base exception for all Queue Me custom exceptions.

    Attributes:
        message: Error message
        detail: Additional error details
        status_code: HTTP status code for API responses
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.message = message if message else _("An error occurred")
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return str(self.message)


class ValidationError(QueueMeError):
    """
    Exception for data validation errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        message = message if message else _("Validation error")
        super().__init__(message, detail, status_code)


class PermissionDeniedError(QueueMeError):
    """
    Exception for permission denied errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_403_FORBIDDEN,
    ):
        message = message if message else _("Permission denied")
        super().__init__(message, detail, status_code)


class ResourceNotFoundError(QueueMeError):
    """
    Exception for resource not found errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_404_NOT_FOUND,
    ):
        message = message if message else _("Resource not found")
        super().__init__(message, detail, status_code)


class DuplicateResourceError(QueueMeError):
    """
    Exception for duplicate resource errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_409_CONFLICT,
    ):
        message = message if message else _("Resource already exists")
        super().__init__(message, detail, status_code)


class ServiceUnavailableError(QueueMeError):
    """
    Exception for service unavailable errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ):
        message = message if message else _("Service unavailable")
        super().__init__(message, detail, status_code)


class RateLimitExceededError(QueueMeError):
    """
    Exception for rate limit exceeded errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_429_TOO_MANY_REQUESTS,
    ):
        message = message if message else _("Rate limit exceeded")
        super().__init__(message, detail, status_code)


class PaymentError(QueueMeError):
    """
    Exception for payment processing errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        message = message if message else _("Payment processing error")
        super().__init__(message, detail, status_code)


class BookingConflictError(QueueMeError):
    """
    Exception for booking conflict errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_409_CONFLICT,
    ):
        message = message if message else _("Booking conflict detected")
        super().__init__(message, detail, status_code)


class UnavailableSlotError(QueueMeError):
    """
    Exception for unavailable time slot errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_409_CONFLICT,
    ):
        message = message if message else _("Time slot unavailable")
        super().__init__(message, detail, status_code)


class InvalidOTPError(QueueMeError):
    """
    Exception for invalid OTP errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        message = message if message else _("Invalid OTP code")
        super().__init__(message, detail, status_code)


class ExpiredOTPError(QueueMeError):
    """
    Exception for expired OTP errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        message = message if message else _("OTP code has expired")
        super().__init__(message, detail, status_code)


class FileValidationError(QueueMeError):
    """
    Exception for file validation errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        message = message if message else _("Invalid file")
        super().__init__(message, detail, status_code)


class ConfigurationError(QueueMeError):
    """
    Exception for system configuration errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        message = message if message else _("System configuration error")
        super().__init__(message, detail, status_code)


class ExternalServiceError(QueueMeError):
    """
    Exception for external service integration errors.
    """

    def __init__(
        self,
        message: str = None,
        detail: Any = None,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ):
        message = message if message else _("External service error")
        super().__init__(message, detail, status_code)
