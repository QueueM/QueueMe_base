"""
Global exception handler for the Queue Me platform.

This module provides a custom exception handler for DRF that handles
custom exceptions and provides consistent error responses.
"""

import logging
import traceback

from django.core.exceptions import (
    PermissionDenied,
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import DatabaseError, IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .custom_exceptions import APIException

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    """
    Custom exception handler for DRF views.

    Handles both DRF and custom exceptions, providing consistent response format.

    Args:
        exc: The exception
        context: The exception context

    Returns:
        Response: Consistent error response
    """
    # Try the default DRF exception handler
    response = drf_exception_handler(exc, context)

    # If the exception is a DRF exception, prepare a consistent response
    if response is not None:
        data = {
            "message": str(exc),
            "status_code": response.status_code,
            "code": exc.__class__.__name__,
        }

        # Include validation errors if available
        if isinstance(exc, ValidationError):
            data["errors"] = exc.detail

        response.data = data
        return response

    # Handle custom APIException
    if isinstance(exc, APIException):
        logger.warning(f"API Exception: {str(exc)}")
        return Response(exc.to_dict(), status=exc.status_code)

    # Handle Django's built-in exceptions
    if isinstance(exc, Http404):
        logger.info(f"Resource not found: {str(exc)}")
        return Response(
            {
                "message": "Not found",
                "status_code": status.HTTP_404_NOT_FOUND,
                "code": "NotFound",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, PermissionDenied):
        logger.warning(f"Permission denied: {str(exc)}")
        return Response(
            {
                "message": str(exc)
                or "You do not have permission to perform this action",
                "status_code": status.HTTP_403_FORBIDDEN,
                "code": "PermissionDenied",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, DjangoValidationError):
        logger.info(f"Validation error: {str(exc)}")
        return Response(
            {
                "message": "Validation error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "code": "ValidationError",
                "errors": (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": exc.messages}
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Handle database-related exceptions
    if isinstance(exc, IntegrityError):
        logger.warning(f"Database integrity error: {str(exc)}")
        return Response(
            {
                "message": "A conflict occurred with the existing data",
                "status_code": status.HTTP_409_CONFLICT,
                "code": "IntegrityError",
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, DatabaseError):
        logger.error(f"Database error: {str(exc)}")
        return Response(
            {
                "message": "Database error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "code": "DatabaseError",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Handle unhandled exceptions
    logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")
    return Response(
        {
            "message": "An unexpected error occurred",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "code": "InternalServerError",
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
    logger.error(
        f"Exception for {request.method} {request.path}: {str(exception)}\n"
        f"User: {request.user if request.user.is_authenticated else 'Anonymous'}\n"
        f"Traceback: {traceback.format_exc()}"
    )
