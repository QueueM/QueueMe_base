"""
Custom exceptions for the Queue Me platform.

This module defines a hierarchy of custom exceptions used across the platform
to provide consistent error handling and reporting.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import status


class APIException(Exception):
    """Base exception for all API-related exceptions."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = _("An unexpected error occurred.")

    def __init__(self, message=None, status_code=None, errors=None):
        self.message = message or self.default_message
        if status_code:
            self.status_code = status_code
        self.errors = errors
        super().__init__(self.message)

    def to_dict(self):
        """Convert exception to dictionary representation."""
        error_dict = {
            "message": str(self.message),
            "status_code": self.status_code,
            "code": self.__class__.__name__,
        }

        if self.errors:
            error_dict["errors"] = self.errors

        return error_dict


class InvalidDataException(APIException):
    """Exception raised when request data is invalid."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = _("Invalid data provided.")


class ResourceNotFoundException(APIException):
    """Exception raised when a requested resource is not found."""

    status_code = status.HTTP_404_NOT_FOUND
    default_message = _("The requested resource was not found.")


class PermissionDeniedException(APIException):
    """Exception raised when user doesn't have permission for an action."""

    status_code = status.HTTP_403_FORBIDDEN
    default_message = _("You do not have permission to perform this action.")


class ValidationException(APIException):
    """Exception raised for validation errors."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = _("Validation failed.")


class ServiceUnavailableException(APIException):
    """Exception raised when a service is unavailable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = _("The service is currently unavailable.")


class DuplicateResourceException(APIException):
    """Exception raised when attempting to create a duplicate resource."""

    status_code = status.HTTP_409_CONFLICT
    default_message = _("A resource with this identifier already exists.")


class InvalidOperationException(APIException):
    """Exception raised when an operation is invalid in the current state."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = _("This operation is not valid in the current state.")


class ThrottledException(APIException):
    """Exception raised when rate limit is exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = _("Rate limit exceeded. Please try again later.")


class PaymentException(APIException):
    """Exception raised for payment-related errors."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_message = _("Payment error occurred.")


class AuthenticationException(APIException):
    """Exception raised for authentication errors."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = _("Authentication failed.")


class SchedulingConflictException(APIException):
    """Exception raised when there's a scheduling conflict."""

    status_code = status.HTTP_409_CONFLICT
    default_message = _("A scheduling conflict was detected.")


class NoAvailabilityException(APIException):
    """Exception raised when there's no availability for a service."""

    status_code = status.HTTP_409_CONFLICT
    default_message = _("No availability found for the requested time period.")


class ExternalServiceException(APIException):
    """Exception raised when an external service fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = _("Error occurred with an external service.")


class FeatureNotAvailableException(APIException):
    """Exception raised when a feature is not available in current subscription."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_message = _(
        "This feature is not available in your current subscription plan."
    )


class QuotaExceededException(APIException):
    """Exception raised when a quota is exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = _("You have exceeded your quota for this resource.")


class MediaProcessingException(APIException):
    """Exception raised when media processing fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = _("Failed to process media file.")


class LocationException(APIException):
    """Exception raised for location-related errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = _("Location error occurred.")


class IncompatibleServiceException(APIException):
    """Exception raised when services are incompatible."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = _("The selected services are incompatible.")
