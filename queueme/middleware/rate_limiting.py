"""
Rate limiting middleware to protect against abuse.
Implements different rate limits for different types of requests.
"""

import time
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin


class RateLimiter(ABC):
    """Base rate limiter interface."""

    @abstractmethod
    def is_rate_limited(self, request: HttpRequest) -> bool:
        """
        Check if the request should be rate limited.

        Args:
            request: The HTTP request

        Returns:
            True if rate limited, False otherwise
        """
        pass


class IPRateLimiter(RateLimiter):
    """Rate limiter based on client IP address."""

    def __init__(self, rate: int, period: int, prefix: str = "rl:"):
        """
        Initialize the IP rate limiter.

        Args:
            rate: Maximum number of requests
            period: Time period in seconds
            prefix: Cache key prefix
        """
        self.rate = rate
        self.period = period
        self.prefix = prefix

    def is_rate_limited(self, request: HttpRequest) -> bool:
        """
        Check if the request from this IP exceeds rate limits.

        Args:
            request: The HTTP request

        Returns:
            True if rate limited, False otherwise
        """
        # Get client IP from X-Forwarded-For if behind proxy, otherwise from META
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "")

        if not client_ip:
            # If no IP can be determined, don't rate limit
            return False

        # Create a cache key for this IP
        cache_key = f"{self.prefix}{client_ip}"
        cache_value = cache.get(cache_key, {"count": 0, "timestamp": time.time()})

        # Check if period has elapsed, reset if needed
        current_time = time.time()
        if current_time - cache_value["timestamp"] > self.period:
            cache_value = {"count": 0, "timestamp": current_time}

        # Increment counter
        cache_value["count"] += 1
        cache.set(cache_key, cache_value, self.period)

        # Return True if rate limit exceeded
        return cache_value["count"] > self.rate


class SensitiveEndpointLimiter(RateLimiter):
    """
    Rate limiter specifically for sensitive endpoints like OTP verification.
    Stricter limits for these endpoints.
    """

    def __init__(self, rate: int = 5, period: int = 60, lockout_time: int = 600):
        """
        Initialize the sensitive endpoint limiter.

        Args:
            rate: Maximum number of requests
            period: Time period in seconds
            lockout_time: Lockout time in seconds after rate limit exceeded
        """
        self.rate = rate
        self.period = period
        self.lockout_time = lockout_time
        self.prefix = "rl:sensitive:"

    def is_rate_limited(self, request: HttpRequest) -> bool:
        """
        Check if this sensitive endpoint request should be rate limited.

        Args:
            request: The HTTP request

        Returns:
            True if rate limited, False otherwise
        """
        # Extract identifier (phone number from request body OR IP address)
        phone_number = None
        if request.method == "POST" and hasattr(request, "body"):
            try:
                import json

                body = json.loads(request.body.decode("utf-8"))
                phone_number = body.get("phone_number")
            except (json.JSONDecodeError, UnicodeDecodeError):
                phone_number = None

        identifier = (
            phone_number
            or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "")
        )

        if not identifier:
            return False

        # Create cache keys
        attempts_key = f"{self.prefix}attempts:{identifier}"
        lockout_key = f"{self.prefix}lockout:{identifier}"

        # Check if user is locked out
        if cache.get(lockout_key):
            return True

        # Get and update attempt count
        attempts = cache.get(attempts_key, 0)
        attempts += 1
        cache.set(attempts_key, attempts, self.period)

        # Lockout if too many attempts
        if attempts > self.rate:
            cache.set(lockout_key, True, self.lockout_time)
            return True

        return False


class RateLimitingMiddleware(MiddlewareMixin):
    """Middleware to apply rate limiting to requests."""

    def __init__(self, get_response=None):
        """Initialize the middleware with rate limiters for different paths."""
        super().__init__(get_response)
        self.rate_limiters = {}

        # Global rate limit for all requests
        self.default_limiter = IPRateLimiter(
            rate=getattr(settings, "RATE_LIMIT_DEFAULT_RATE", 60),
            period=getattr(settings, "RATE_LIMIT_DEFAULT_PERIOD", 60),
            prefix="rl:global:",
        )

        # Register path-specific rate limiters
        self._register_rate_limiters()

    def _register_rate_limiters(self):
        """Register rate limiters for specific paths."""
        # API rate limiter - stricter than default
        self.rate_limiters["/api/"] = IPRateLimiter(
            rate=getattr(settings, "RATE_LIMIT_API_RATE", 30),
            period=getattr(settings, "RATE_LIMIT_API_PERIOD", 60),
            prefix="rl:api:",
        )

        # Auth endpoints - sensitive, use special limiter
        self.rate_limiters["/api/v1/auth/send-otp/"] = SensitiveEndpointLimiter(
            rate=getattr(settings, "RATE_LIMIT_OTP_RATE", 5),
            period=getattr(settings, "RATE_LIMIT_OTP_PERIOD", 300),  # 5 minutes
            lockout_time=getattr(settings, "RATE_LIMIT_OTP_LOCKOUT", 1800),  # 30 minutes
        )

        self.rate_limiters["/api/v1/auth/verify-otp/"] = SensitiveEndpointLimiter(
            rate=getattr(settings, "RATE_LIMIT_OTP_VERIFY_RATE", 5),
            period=getattr(settings, "RATE_LIMIT_OTP_VERIFY_PERIOD", 300),
            lockout_time=getattr(settings, "RATE_LIMIT_OTP_VERIFY_LOCKOUT", 1800),
        )

    def process_request(self, request):
        """
        Process request and apply rate limiting if needed.

        Args:
            request: The HTTP request

        Returns:
            JsonResponse with error if rate limited, None otherwise
        """
        # Skip rate limiting for staff/admin users
        if hasattr(request, "user") and request.user.is_authenticated and request.user.is_staff:
            return None

        # Find the most specific rate limiter for this path
        limiter = self.default_limiter
        for path, path_limiter in self.rate_limiters.items():
            if request.path.startswith(path):
                limiter = path_limiter
                break

        # Check if rate limited
        if limiter.is_rate_limited(request):
            return JsonResponse(
                {"error": "Rate limit exceeded. Please try again later."}, status=429
            )

        return None
