"""
Function decorators for Queue Me platform.

This module provides decorators for common patterns like permission checking,
error handling, performance monitoring, and rate limiting.
"""

import functools
import logging
import time
from typing import Callable, List, Optional, Type

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import QueueMeError, RateLimitExceededError

logger = logging.getLogger(__name__)
User = get_user_model()


def require_permission(resource: str, action: str):
    """
    Decorator to check if user has permission to access a resource.

    Args:
        resource: Resource name
        action: Action name

    Returns:
        Decorated function
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            # Import here to avoid circular imports
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            if not PermissionResolver.has_permission(user, resource, action):
                raise PermissionDenied("You do not have permission to perform this action.")

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator


def require_shop_permission(resource: str, action: str):
    """
    Decorator to check if user has permission for shop-specific resource.

    Args:
        resource: Resource name
        action: Action name

    Returns:
        Decorated function
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            # Get shop_id from URL kwargs or query params
            shop_id = kwargs.get("shop_id") or request.query_params.get("shop_id")

            if not shop_id:
                raise PermissionDenied("Shop ID is required.")

            # Import here to avoid circular imports
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            if not PermissionResolver.has_shop_permission(user, shop_id, resource, action):
                raise PermissionDenied(
                    "You do not have permission to perform this action for this shop."
                )

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator to log the execution time of a function.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time

        # Log execution time
        logger.debug(
            f"{func.__module__}.{func.__qualname__} executed in {execution_time:.4f} seconds"
        )

        # If execution time is high, log a warning
        if execution_time > 1.0:  # 1 second threshold
            logger.warning(
                f"Slow execution: {func.__module__}.{func.__qualname__} took {execution_time:.4f} seconds"
            )

        return result

    return wrapper


def handle_exceptions(
    exceptions: Optional[List[Type[Exception]]] = None,
    default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    log_exceptions: bool = True,
):
    """
    Decorator to handle exceptions in API views.

    Args:
        exceptions: List of exception types to handle
        default_status: Default HTTP status code for unspecified exceptions
        log_exceptions: Whether to log exceptions

    Returns:
        Decorated function
    """
    if exceptions is None:
        exceptions = [Exception]

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            try:
                return view_func(view, request, *args, **kwargs)
            except tuple(exceptions) as e:
                # Determine status code
                if isinstance(e, QueueMeError):
                    status_code = e.status_code
                else:
                    status_code = default_status

                # Log the exception
                if log_exceptions:
                    logger.exception(f"Exception in {view_func.__name__}: {str(e)}")

                # Return error response
                if isinstance(request, (HttpRequest, Request)):
                    # For API views, return JSON response
                    if isinstance(e, QueueMeError):
                        error_detail = e.detail
                    else:
                        error_detail = str(e)

                    if isinstance(view, APIView):
                        return Response({"detail": error_detail}, status=status_code)
                    else:
                        return JsonResponse({"detail": error_detail}, status=status_code)
                else:
                    # For non-HTTP functions, re-raise
                    raise

        return _wrapped_view

    return decorator


def atomic_transaction(using: Optional[str] = None):
    """
    Decorator to execute a function within a database transaction.

    Args:
        using: Database alias to use

    Returns:
        Decorated function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with transaction.atomic(using=using):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def rate_limit(key: str, limit: str, block: bool = True):
    """
    Decorator to apply rate limiting to a view function.

    Args:
        key: Rate limit key (e.g., 'auth', 'otp')
        limit: Rate limit string (e.g., '10/min', '100/hour')
        block: Whether to block requests that exceed the limit

    Returns:
        Decorated function
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            # Parse rate limit
            try:
                count, period = limit.split("/")
                count = int(count)

                if period.lower() in ("s", "sec", "second", "seconds"):
                    period_seconds = 1
                elif period.lower() in ("m", "min", "minute", "minutes"):
                    period_seconds = 60
                elif period.lower() in ("h", "hour", "hours"):
                    period_seconds = 3600
                elif period.lower() in ("d", "day", "days"):
                    period_seconds = 86400
                else:
                    period_seconds = 60  # Default to minutes
            except (ValueError, AttributeError):
                # Default to 60 requests per minute
                count = 60
                period_seconds = 60

            # Generate cache key
            if hasattr(request, "user") and request.user.is_authenticated:
                # User-based rate limiting
                cache_key = f"rate_limit:{key}:user:{request.user.id}"
            else:
                # IP-based rate limiting
                ip = request.META.get("REMOTE_ADDR", "")
                cache_key = f"rate_limit:{key}:ip:{ip}"

            # Check current request count
            current = cache.get(cache_key, 0)

            if current >= count:
                # Rate limit exceeded
                if block:
                    raise RateLimitExceededError(f"Rate limit exceeded for {key}")
                else:
                    # Log but don't block
                    logger.warning(f"Rate limit exceeded for {key} by {cache_key}")

            # Increment counter
            if current == 0:
                # First request in this period
                cache.set(cache_key, 1, period_seconds)
            else:
                # Increment existing counter
                cache.incr(cache_key)

            # Execute view
            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator
