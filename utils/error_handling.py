"""
Standardized error handling utilities for QueueMe.

This module provides consistent error handling patterns to be used throughout the application.
"""

import functools
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class QueueMeError(Exception):
    """Base class for all QueueMe application errors."""

    def __init__(self, message: str, code: str = "error", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ResourceNotFoundError(QueueMeError):
    """Error raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(message=message, code="not_found", status_code=404)


class AuthenticationError(QueueMeError):
    """Error raised when authentication fails."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, code="authentication_required", status_code=401)


class AuthorizationError(QueueMeError):
    """Error raised when a user doesn't have permission for an action."""

    def __init__(self, message: str = "You don't have permission to perform this action"):
        super().__init__(message=message, code="permission_denied", status_code=403)


class ValidationFailedError(QueueMeError):
    """Error raised when validation fails."""

    def __init__(
        self, message: str = "Validation failed", errors: Optional[Dict[str, List[str]]] = None
    ):
        self.errors = errors or {}
        super().__init__(message=message, code="validation_failed", status_code=400)


class RateLimitExceededError(QueueMeError):
    """Error raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message=message, code="rate_limit_exceeded", status_code=429)


class DatabaseOperationError(QueueMeError):
    """Error raised when a database operation fails."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message=message, code="database_error", status_code=500)


class ServiceUnavailableError(QueueMeError):
    """Error raised when an external service is unavailable."""

    def __init__(self, service_name: str, message: Optional[str] = None):
        if message is None:
            message = f"Service {service_name} is currently unavailable"
        super().__init__(message=message, code="service_unavailable", status_code=503)


def api_error_response(error: Exception) -> Response:
    """
    Convert an exception to a standardized API error response.

    Args:
        error: The exception to convert

    Returns:
        Standardized API response
    """
    if isinstance(error, QueueMeError):
        data = {
            "success": False,
            "error": {
                "code": error.code,
                "message": error.message,
            },
        }

        # Add validation errors if available
        if isinstance(error, ValidationFailedError) and error.errors:
            data["error"]["errors"] = error.errors

        # Add retry-after header for rate limit errors
        if isinstance(error, RateLimitExceededError):
            return Response(
                data, status=error.status_code, headers={"Retry-After": str(error.retry_after)}
            )

        return Response(data, status=error.status_code)

    # Handle Django exceptions
    if isinstance(error, ObjectDoesNotExist):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "not_found",
                    "message": str(error),
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(error, PermissionDenied):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "permission_denied",
                    "message": str(error) or "You don't have permission to perform this action",
                },
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(error, ValidationError):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "validation_failed",
                    "message": "Validation failed",
                    "errors": error.message_dict
                    if hasattr(error, "message_dict")
                    else {"detail": [str(error)]},
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(error, DatabaseError):
        logger.error(f"Database error: {str(error)}", exc_info=True)
        return Response(
            {
                "success": False,
                "error": {
                    "code": "database_error",
                    "message": "A database error occurred",
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Handle DRF exceptions
    if isinstance(error, APIException):
        return Response(
            {
                "success": False,
                "error": {
                    "code": error.default_code,
                    "message": str(error),
                },
            },
            status=error.status_code,
        )

    # Handle unexpected exceptions
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    return Response(
        {
            "success": False,
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred",
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def handle_api_exceptions(view_func):
    """
    Decorator to catch exceptions in API views and return standardized error responses.

    Args:
        view_func: The view function to wrap

    Returns:
        Wrapped function that handles exceptions
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            return api_error_response(e)

    return wrapper


def transaction_with_retry(max_retries: int = 3, retry_delay: float = 0.1) -> Callable:
    """
    Decorator for functions that should be executed in a transaction with retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Decorator function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time

            last_error = None
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                except (DatabaseError, IntegrityError) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Database error in {func.__name__}, retrying "
                            f"(attempt {attempt+1}/{max_retries}): {str(e)}"
                        )
                        # Wait before retrying with exponential backoff
                        time.sleep(retry_delay * (2**attempt))
                    else:
                        logger.error(
                            f"Database error in {func.__name__} after {max_retries} attempts: {str(e)}",
                            exc_info=True,
                        )

            # If we got here, all retries failed
            raise DatabaseOperationError(
                f"Database operation failed after {max_retries} attempts"
            ) from last_error

        return wrapper

    return decorator


def log_exception(
    logger_name: Optional[str] = None, level: str = "error", include_traceback: bool = True
) -> Callable:
    """
    Decorator to log exceptions with consistent formatting.

    Args:
        logger_name: Optional name of logger to use (defaults to current module's logger)
        level: Logging level to use
        include_traceback: Whether to include traceback in the log

    Returns:
        Decorator function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get the appropriate logger
                log = logging.getLogger(logger_name or func.__module__)

                # Get the appropriate logging method
                log_method = getattr(log, level.lower())

                # Format the error message
                message = f"Error in {func.__name__}: {str(e)}"

                # Log with or without traceback
                if include_traceback:
                    log_method(message, exc_info=True)
                else:
                    log_method(message)

                # Re-raise the exception
                raise

        return wrapper

    return decorator
