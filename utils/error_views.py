"""
Error views and utilities for Queue Me platform.

This module defines custom error views for handling HTTP errors and utilities
for standardized error response formatting.
"""

import logging
import traceback
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import translation
from django.views.decorators.csrf import requires_csrf_token
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .constants import ERROR_MESSAGES

logger = logging.getLogger(__name__)


@requires_csrf_token
def error_404_view(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Custom 404 error handler.

    Args:
        request: HTTP request
        exception: Exception that caused the error

    Returns:
        HTTP response
    """
    # Get current language
    language = translation.get_language()

    # Log the 404 error
    logger.warning(
        f"404 Error: {request.path} - Referrer: {request.META.get('HTTP_REFERER', 'None')}"
    )

    # Check if API request (based on path or Accept header)
    is_api_request = request.path.startswith(
        "/api/"
    ) or "application/json" in request.META.get("HTTP_ACCEPT", "")

    if is_api_request:
        # Return JSON response for API requests
        return JsonResponse(
            {
                "error": "not_found",
                "detail": ERROR_MESSAGES["not_found"].get(
                    language, ERROR_MESSAGES["not_found"]["en"]
                ),
                "path": request.path,
            },
            status=404,
        )
    else:
        # Return HTML response for web requests
        return render(request, "errors/404.html", {"path": request.path}, status=404)


@requires_csrf_token
def error_500_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """
    Custom 500 error handler.

    Args:
        request: HTTP request

    Returns:
        HTTP response
    """
    # Get current language
    language = translation.get_language()

    # Log the 500 error with traceback
    error_message = "Internal server error"
    if "exc_info" in kwargs:
        error_message = str(kwargs["exc_info"][1])
        logger.error(f"500 Error: {error_message}\n{traceback.format_exc()}")
    else:
        logger.error(f"500 Error in {request.path}\n{traceback.format_exc()}")

    # Check if API request
    is_api_request = request.path.startswith(
        "/api/"
    ) or "application/json" in request.META.get("HTTP_ACCEPT", "")

    if is_api_request:
        # Return JSON response for API requests
        response_data = {
            "error": "server_error",
            "detail": ERROR_MESSAGES["service_unavailable"].get(
                language, ERROR_MESSAGES["service_unavailable"]["en"]
            ),
        }

        # Add debug info in development
        if settings.DEBUG:
            response_data["debug"] = error_message

        return JsonResponse(response_data, status=500)
    else:
        # Return HTML response for web requests
        context = {"error_message": error_message if settings.DEBUG else None}
        return render(request, "errors/500.html", context, status=500)


def api_error_response(
    error_code: str,
    message: Optional[str] = None,
    detail: Optional[Union[Dict, List, str]] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    language: Optional[str] = None,
) -> Response:
    """
    Create a standardized error response for API endpoints.

    Args:
        error_code: Error code key
        message: Optional custom message
        detail: Optional error details
        status_code: HTTP status code
        language: Language code

    Returns:
        DRF Response object
    """
    # Get language code or use current language
    if language is None:
        language = translation.get_language() or "en"

    # Get error message from constants or use custom message
    if message is None:
        message = ERROR_MESSAGES.get(error_code, {}).get(
            language, ERROR_MESSAGES.get(error_code, {}).get("en", "An error occurred")
        )

    # Build response data
    response_data = {"error": error_code, "message": message}

    # Add error details if provided
    if detail is not None:
        response_data["detail"] = detail

    return Response(response_data, status=status_code)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.

    Args:
        exc: Exception instance
        context: Context dict including request

    Returns:
        Response object
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)

    # Get request object
    request = context.get("request")
    language = translation.get_language() if request else "en"

    # If no response (DRF couldn't handle it), create one
    if response is None:
        if settings.DEBUG:
            # In debug mode, provide more details
            logger.exception("Unhandled exception in API view")
            response = Response(
                {
                    "error": "server_error",
                    "message": str(exc),
                    "detail": traceback.format_exc(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        else:
            # In production, just provide a generic message
            logger.exception("Unhandled exception in API view")
            response = Response(
                {
                    "error": "server_error",
                    "message": ERROR_MESSAGES["service_unavailable"].get(
                        language, ERROR_MESSAGES["service_unavailable"]["en"]
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        # DRF handled the exception, but we'll standardize the response format
        if isinstance(exc, ValidationError):
            error_code = "validation_error"
        else:
            # Try to get error code from exception class name
            error_code = (
                exc.__class__.__name__.lower()
                .replace("error", "")
                .replace("exception", "")
            )

        # Extract original data
        data = response.data
        status_code = response.status_code

        # Transform to our standard format
        message = ERROR_MESSAGES.get(error_code, {}).get(language, None)
        if not message:
            if hasattr(exc, "detail") and isinstance(exc.detail, str):
                message = exc.detail
            elif "detail" in data and isinstance(data["detail"], str):
                message = data["detail"]
            else:
                message = str(exc)

        # Keep original detail data if available
        detail = None
        if hasattr(exc, "detail") and not isinstance(exc.detail, str):
            detail = exc.detail

        # Create new standard response
        response = Response(
            {
                "error": error_code,
                "message": message,
                **({"detail": detail} if detail is not None else {}),
            },
            status=status_code,
        )

    return response
