"""
Global exception handler for the Queue Me platform.

This module provides a custom exception handler for DRF that handles
custom exceptions and provides consistent error responses.
"""

import logging
import socket
import traceback
from typing import Any, Dict, Optional

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import (
    DatabaseError,
    DataError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
)
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    NotFound,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from utils.constants import ERROR_MESSAGES

from .custom_exceptions import APIException

logger = logging.getLogger(__name__)

# Network related errors
NETWORK_ERRORS = (ConnectionError, Timeout, socket.timeout, socket.error)


def get_error_code(exception: Exception) -> str:
    """
    Get standardized error code from exception.

    Args:
        exception: The exception to get code for

    Returns:
        str: Standardized error code
    """
    if isinstance(exception, ValidationError):
        return "validation_error"
    elif isinstance(exception, PermissionDenied):
        return "permission_denied"
    elif isinstance(exception, Http404) or isinstance(exception, NotFound):
        return "not_found"
    elif isinstance(exception, ObjectDoesNotExist):
        return "not_found"
    elif isinstance(exception, IntegrityError):
        return "integrity_error"
    elif isinstance(exception, DatabaseError):
        return "database_error"
    elif isinstance(exception, DataError):
        return "data_error"
    elif isinstance(exception, NotAuthenticated):
        return "authentication_required"
    elif isinstance(exception, NETWORK_ERRORS):
        return "network_error"
    elif isinstance(exception, APIException):
        return exception.error_code
    else:
        # Convert exception class name to snake case
        return (
            exception.__class__.__name__.lower()
            .replace("error", "")
            .replace("exception", "")
        )


def get_error_message(exception: Exception, error_code: str) -> str:
    """
    Get localized error message for exception.

    Args:
        exception: The exception
        error_code: The error code

    Returns:
        str: Localized error message
    """
    # Try to get message from ERROR_MESSAGES
    if error_code in ERROR_MESSAGES:
        return ERROR_MESSAGES[error_code]

    # Try to get message from exception
    if hasattr(exception, "detail") and isinstance(exception.detail, str):
        return exception.detail

    # Handle specific error types with user-friendly messages
    if isinstance(exception, NETWORK_ERRORS):
        return _("Connection error. Please check your network and try again.")
    elif isinstance(exception, IntegrityError):
        return _("A conflict occurred with existing data.")
    elif isinstance(exception, DatabaseError):
        return _("A database error occurred. Please try again later.")
    elif isinstance(exception, ObjectDoesNotExist):
        return _("The requested resource was not found.")

    # Fallback to generic message for production environments
    if hasattr(exception, "__module__") and "django" in exception.__module__:
        return _("An error occurred processing your request.")

    # Fallback to exception string for non-production environments
    return str(exception)


def get_error_details(exception: Exception) -> Optional[Dict[str, Any]]:
    """
    Get detailed error information from exception.

    Args:
        exception: The exception

    Returns:
        Optional[Dict]: Error details if available
    """
    # For validation errors, return formatted validation details
    if (
        isinstance(exception, ValidationError)
        and hasattr(exception, "detail")
        and not isinstance(exception.detail, str)
    ):
        if isinstance(exception.detail, list):
            return {"validation_errors": exception.detail}
        return exception.detail

    # For database integrity errors, try to extract useful information
    if isinstance(exception, IntegrityError):
        error_str = str(exception)
        if "unique constraint" in error_str.lower():
            return {"type": "unique_constraint_violation"}
        elif "foreign key constraint" in error_str.lower():
            return {"type": "foreign_key_constraint_violation"}

    return None


def exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """
    Custom exception handler for DRF views.

    Handles both DRF and custom exceptions, providing consistent response format.

    Args:
        exc: The exception
        context: The exception context

    Returns:
        Response: Consistent error response
    """
    # Handle Django ValidationError by converting to DRF ValidationError
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = ValidationError(detail=exc.message_dict)
        else:
            exc = ValidationError(detail=exc.messages)

    # Try the default DRF exception handler
    response = drf_exception_handler(exc, context)

    # Get error code and message
    error_code = get_error_code(exc)
    error_message = get_error_message(exc, error_code)
    error_details = get_error_details(exc)

    # Log the exception with appropriate level
    if isinstance(
        exc, (ValidationError, Http404, NotFound, NotAuthenticated, PermissionDenied)
    ):
        # Less severe errors
        logger.warning(
            f"Exception: {error_code} - {error_message}\n"
            f"Context: {context}\n"
            f"Details: {error_details}"
        )
    else:
        # More severe errors
        logger.error(
            f"Exception: {error_code} - {error_message}\n"
            f"Context: {context}\n"
            f"Traceback: {traceback.format_exc()}"
        )

    # Handle specific database errors
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "error": error_code,
                "message": _("A conflict occurred with the existing data"),
                "details": error_details or str(exc),
            },
            status=status.HTTP_409_CONFLICT,
        )
    elif isinstance(exc, (OperationalError, ProgrammingError)):
        return Response(
            {
                "error": error_code,
                "message": _("A database error occurred"),
                "details": error_details or str(exc),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    elif isinstance(exc, NETWORK_ERRORS):
        return Response(
            {
                "error": "network_error",
                "message": _(
                    "Network error. Please check your connection and try again."
                ),
                "details": error_details or {"type": "connection_error"},
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # If DRF handled the exception, standardize the response format
    if response is not None:
        response.data = {
            "error": error_code,
            "message": error_message,
            **({"details": error_details} if error_details is not None else {}),
        }
        return response

    # Handle unhandled exceptions
    return Response(
        {
            "error": error_code,
            "message": error_message,
            **({"details": error_details} if error_details is not None else {}),
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def log_exception(request, exception):
    """
    Log exceptions with request details.

    Args:
        request: The request that caused the exception
        exception: The exception that occurred
    """
    user_info = "Anonymous"

    # Get user information if authenticated
    if hasattr(request, "user") and request.user.is_authenticated:
        user_info = f"ID: {request.user.id}, Phone: {getattr(request.user, 'phone_number', 'unknown')}"

    # Get client IP
    client_ip = request.META.get(
        "HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown")
    )

    # Log exception details
    logger.error(
        f"Exception for {request.method} {request.path}: {str(exception)}\n"
        f"User: {user_info}\n"
        f"IP: {client_ip}\n"
        f"User Agent: {request.META.get('HTTP_USER_AGENT', 'unknown')}\n"
        f"Traceback: {traceback.format_exc()}"
    )

    # Record security event for potentially dangerous exceptions
    if isinstance(exception, (PermissionDenied, NotAuthenticated)):
        try:
            from apps.authapp.services.security_service import SecurityService

            SecurityService.record_security_event(
                user_id=(
                    request.user.id
                    if hasattr(request, "user") and request.user.is_authenticated
                    else None
                ),
                event_type="security_exception",
                details={
                    "exception_type": exception.__class__.__name__,
                    "path": request.path,
                    "method": request.method,
                },
                severity="warning",
                ip_address=client_ip,
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except Exception as e:
            logger.error(f"Failed to record security event: {str(e)}")
