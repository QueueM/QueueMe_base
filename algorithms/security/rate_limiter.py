"""
Advanced rate limiting algorithm for Queue Me platform.

This module provides sophisticated rate limiting capabilities with:
- Tiered rate limiting based on user roles
- Exponential backoff for repeated violations
- IP-based and user-based tracking
- Distributed rate limiting using Redis
- Different limits for different endpoint categories
"""

import hashlib
import json
from functools import wraps
from typing import Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import Throttled

# Default rate limits by user role (requests per minute)
DEFAULT_RATE_LIMITS = {
    "anonymous": 30,  # Unauthenticated users
    "customer": 60,  # Regular customers
    "employee": 120,  # Shop employees
    "shop_manager": 300,  # Shop managers
    "company": 300,  # Company owners
    "queue_me_employee": 600,  # Queue Me staff
    "queue_me_admin": 1000,  # Queue Me administrators
}

# Rate limits by endpoint category (requests per minute)
ENDPOINT_RATE_LIMITS = {
    "auth": {
        "anonymous": 5,  # Login/signup attempts
        "customer": 10,
        "default": 5,
    },
    "booking": {
        "anonymous": 10,
        "customer": 20,
        "employee": 100,
        "default": 20,
    },
    "queue": {
        "anonymous": 20,
        "customer": 40,
        "employee": 200,
        "default": 40,
    },
    "content": {  # Reels, stories, etc.
        "anonymous": 50,
        "customer": 100,
        "default": 50,
    },
    # Special case for OTP to prevent abuse
    "otp": {
        "anonymous": 3,  # 3 attempts per minute
        "customer": 3,
        "default": 3,
    },
}

# Exponential backoff settings
BACKOFF_MULTIPLIER = 2  # Each violation doubles the penalty period
MAX_BACKOFF_MINUTES = 60  # Maximum 1 hour backoff


class RateLimiter:
    """
    Sophisticated rate limiting implementation with tiered rates,
    multiple tracking strategies, and exponential backoff.
    """

    def __init__(self, redis_client=None):
        """
        Initialize the rate limiter.

        Args:
            redis_client: Optional Redis client for distributed rate limiting.
                          If None, falls back to Django's cache.
        """
        self.redis = redis_client
        self.use_redis = redis_client is not None
        self.cache = cache

    def _get_cache_key(self, identifier: str, category: str) -> str:
        """
        Generate a cache key for rate limiting.

        Args:
            identifier: User ID, IP address, or combined key
            category: Endpoint category (auth, booking, etc.)

        Returns:
            A unique cache key string
        """
        return f"ratelimit:{category}:{identifier}"

    def _get_violation_key(self, identifier: str) -> str:
        """
        Generate a cache key for tracking violations.

        Args:
            identifier: User ID or IP address

        Returns:
            A unique cache key string for violations
        """
        return f"ratelimit_violations:{identifier}"

    def _get_identifier(self, request: HttpRequest) -> Tuple[str, str]:
        """
        Extract identifier from request for rate limiting.

        Uses user ID for authenticated users, IP for anonymous users,
        or a combination for suspicious patterns.

        Args:
            request: Django HTTP request

        Returns:
            Tuple of (identifier, user_role)
        """
        # Get IP address with forwarded proxy support
        ip = self._get_client_ip(request)

        # Get user if authenticated
        user = getattr(request, "user", None)
        user_id = (
            str(user.id)
            if user and hasattr(user, "id") and user.is_authenticated
            else None
        )

        # Determine user role
        role = (
            getattr(user, "user_type", "anonymous")
            if user and user.is_authenticated
            else "anonymous"
        )

        # Use appropriate identifier based on authentication
        if user_id:
            # For authenticated users, primary identifier is user ID
            identifier = f"user:{user_id}"
            # But also check IP to detect suspicious behavior where
            # many user accounts may be used from same IP
            ip_key = f"ip:{ip}"
            self._increment_count(ip_key, "auth", 1, 86400)  # Track IP for 24 hours
        else:
            # For anonymous users, use IP address
            identifier = f"ip:{ip}"

        return identifier, role

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Extract client IP address from request, considering forwarded headers.

        Args:
            request: Django HTTP request

        Returns:
            Client IP address string
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "0.0.0.0")

        return ip

    def _increment_count(
        self, identifier: str, category: str, increment: int = 1, expiry: int = 60
    ) -> int:
        """
        Increment the counter for rate limiting.

        Args:
            identifier: User ID or IP string
            category: Endpoint category (auth, booking, etc.)
            increment: Amount to increment (default 1)
            expiry: Time in seconds before key expires (default 60s)

        Returns:
            The new count after incrementing
        """
        cache_key = self._get_cache_key(identifier, category)

        if self.use_redis:
            # Use Redis pipeline for atomicity
            pipe = self.redis.pipeline()
            pipe.incr(cache_key, increment)
            pipe.expire(cache_key, expiry)
            result = pipe.execute()
            return result[0]  # Return the result of the INCR
        else:
            # Use Django's cache
            count = cache.get(cache_key, 0) + increment
            cache.set(cache_key, count, expiry)
            return count

    def _get_count(self, identifier: str, category: str) -> int:
        """
        Get the current count for an identifier and category.

        Args:
            identifier: User ID or IP string
            category: Endpoint category

        Returns:
            Current count (integer)
        """
        cache_key = self._get_cache_key(identifier, category)

        if self.use_redis:
            count = self.redis.get(cache_key)
            return int(count) if count else 0
        else:
            return cache.get(cache_key, 0)

    def _record_violation(self, identifier: str) -> int:
        """
        Record a rate limit violation and implement exponential backoff.

        Args:
            identifier: User ID or IP string

        Returns:
            The backoff time in seconds
        """
        violation_key = self._get_violation_key(identifier)

        # Get current violation count
        violations = cache.get(violation_key, 0) + 1

        # Calculate backoff time (exponential)
        backoff_minutes = min(
            BACKOFF_MULTIPLIER ** (violations - 1), MAX_BACKOFF_MINUTES
        )
        backoff_seconds = int(backoff_minutes * 60)

        # Store updated violation count with expiry
        # The expiry is longer than the backoff to track repeated offenders
        cache.set(violation_key, violations, backoff_seconds * 2)

        return backoff_seconds

    def _get_backoff_time(self, identifier: str) -> int:
        """
        Get current backoff time for an identifier if in a violation state.

        Args:
            identifier: User ID or IP string

        Returns:
            Backoff time in seconds or 0 if no active backoff
        """
        violation_key = self._get_violation_key(identifier)
        violations = cache.get(violation_key, 0)

        if violations > 0:
            # Calculate current backoff time
            backoff_minutes = min(
                BACKOFF_MULTIPLIER ** (violations - 1), MAX_BACKOFF_MINUTES
            )
            return int(backoff_minutes * 60)

        return 0

    def _get_rate_limit(self, role: str, category: str) -> int:
        """
        Get the rate limit for a role and category.

        Args:
            role: User role (anonymous, customer, etc.)
            category: Endpoint category

        Returns:
            Rate limit (requests per minute)
        """
        # Check category-specific limits first
        if category in ENDPOINT_RATE_LIMITS:
            category_limits = ENDPOINT_RATE_LIMITS[category]
            # Use role-specific limit if available, otherwise default
            return category_limits.get(
                role, category_limits.get("default", DEFAULT_RATE_LIMITS.get(role, 30))
            )

        # Fall back to default limits
        return DEFAULT_RATE_LIMITS.get(role, 30)

    def check_rate_limit(
        self, request: HttpRequest, category: str = "default"
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if a request exceeds the rate limit.

        Args:
            request: Django HTTP request
            category: Endpoint category (auth, booking, etc.)

        Returns:
            Tuple of (is_allowed, retry_after)
            - is_allowed: True if request is allowed, False if rate limited
            - retry_after: Seconds to wait before retrying (None if allowed)
        """
        # Get identifier and user role
        identifier, role = self._get_identifier(request)

        # Check if in backoff period from previous violations
        backoff_time = self._get_backoff_time(identifier)
        if backoff_time > 0:
            return False, backoff_time

        # Get applicable rate limit
        rate_limit = self._get_rate_limit(role, category)

        # Get current count
        current_count = self._get_count(identifier, category)

        # Check if limit exceeded
        if current_count >= rate_limit:
            # Record violation for repeated offenders
            if current_count >= rate_limit * 2:  # Significant overage
                backoff_time = self._record_violation(identifier)
                return False, backoff_time

            # Calculate retry after (time remaining in the minute window)
            retry_after = 60
            return False, retry_after

        # Increment counter
        self._increment_count(identifier, category)

        # Request is allowed
        return True, None

    def reset_counts(self, identifier: str, category: str = None) -> None:
        """
        Reset rate limiting counts for an identifier.

        Args:
            identifier: User ID or IP string
            category: Optional category to reset (None for all)
        """
        if category:
            cache_key = self._get_cache_key(identifier, category)
            cache.delete(cache_key)
        else:
            # For Redis, we would use pattern matching to delete all keys
            # For Django cache, we need to know all categories used
            categories = list(ENDPOINT_RATE_LIMITS.keys()) + ["default"]
            for cat in categories:
                cache_key = self._get_cache_key(identifier, cat)
                cache.delete(cache_key)


# Create a global instance
limiter = RateLimiter()


def rate_limit(category: str = "default"):
    """
    Decorator for rate limiting Django REST framework views.

    Args:
        category: Endpoint category for specific rate limits

    Returns:
        Decorated function
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(view, request, *args, **kwargs):
            # Skip rate limiting in debug mode if configured
            if getattr(settings, "DISABLE_RATE_LIMITING", False) and settings.DEBUG:
                return view_func(view, request, *args, **kwargs)

            # Check rate limit
            is_allowed, retry_after = limiter.check_rate_limit(request, category)

            if not is_allowed:
                # Create error response with retry information
                detail = _(
                    "Request was throttled. Expected available in {seconds} seconds."
                ).format(seconds=retry_after)

                # Use DRF's throttled exception
                raise Throttled(wait=retry_after, detail=detail)

            # Proceed with the view
            return view_func(view, request, *args, **kwargs)

        return wrapped_view

    return decorator


def otp_rate_limit(phone_number: str) -> Tuple[bool, Optional[int]]:
    """
    Specialized rate limiting for OTP generation.

    Args:
        phone_number: User's phone number

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
    # Hash phone number to protect PII in cache
    phone_hash = hashlib.sha256(phone_number.encode()).hexdigest()
    identifier = f"otp:{phone_hash}"

    # Enforce a strict rate limit for OTP requests
    otp_limit = ENDPOINT_RATE_LIMITS.get("otp", {}).get("default", 3)

    # Get current count (separate from general rate limiting)
    count_key = f"ratelimit:otp:{identifier}"
    current_count = cache.get(count_key, 0)

    if current_count >= otp_limit:
        # Calculate time remaining in the minute window (simplified)
        retry_after = 60

        # Record violation for repeated offenders
        if current_count >= otp_limit * 2:
            violation_key = f"ratelimit_violations:{identifier}"
            violations = cache.get(violation_key, 0) + 1
            backoff_minutes = min(
                BACKOFF_MULTIPLIER ** (violations - 1), MAX_BACKOFF_MINUTES
            )
            retry_after = int(backoff_minutes * 60)

            # Update violation count
            cache.set(violation_key, violations, retry_after * 2)

        return False, retry_after

    # Increment counter
    cache.set(count_key, current_count + 1, 60)

    # Request is allowed
    return True, None


class RateLimitMiddleware:
    """
    Middleware for global rate limiting across all requests.

    This provides a fallback protection even for views that
    don't use the rate_limit decorator.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for internal requests, admin paths, and static/media files
        path = request.path_info.lstrip("/")
        if (
            request.META.get("REMOTE_ADDR") == "127.0.0.1"
            or path.startswith(("admin/", "static/", "media/"))
            or getattr(settings, "DISABLE_RATE_LIMITING", False)
            and settings.DEBUG
        ):
            return self.get_response(request)

        # Apply global rate limit
        is_allowed, retry_after = limiter.check_rate_limit(request)

        if not is_allowed:
            if "application/json" in request.META.get("HTTP_ACCEPT", ""):
                # Return JSON response for API requests
                content = {
                    "detail": _(
                        "Request was throttled. Expected available in {seconds} seconds."
                    ).format(seconds=retry_after)
                }
                return HttpResponse(
                    content=json.dumps(content),
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                    content_type="application/json",
                )
            else:
                # Return simple HTTP response for other requests
                content = _(
                    "Too many requests. Please try again in {seconds} seconds."
                ).format(seconds=retry_after)
                return HttpResponse(
                    content=content,
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                    content_type="text/plain",
                )

        # Proceed with request
        return self.get_response(request)
