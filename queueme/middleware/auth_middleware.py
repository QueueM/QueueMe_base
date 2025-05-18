"""
Authentication middleware for Queue Me platform.

This middleware handles JWT authentication for API requests,
role-based access control, and security features like rate limiting.
"""

import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.authapp.services.token_service import TokenService

logger = logging.getLogger(__name__)


class JWTAuthMiddleware(MiddlewareMixin):
    """
    Middleware for handling JWT authentication for API requests.

    Authenticates users via JWT tokens and sets the user on the request object.
    Exempt paths (like authentication endpoints) do not require authentication.
    """

    # Rate limiting settings
    RATE_LIMIT_WINDOW = 60  # 1 minute
    MAX_REQUESTS_PER_WINDOW = 100
    RATE_LIMIT_CACHE_PREFIX = "rate_limit:"

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.rate_limit_cache = defaultdict(list)

    def process_request(self, request):
        # Performance tracking
        request._auth_start_time = time.time()

        # Skip authentication for non-API endpoints
        if not request.path.startswith("/api/"):
            return None

        # Skip authentication for explicitly exempted paths
        exempt_paths = [
            r"^/api/auth/request_otp/?$",
            r"^/api/auth/verify_otp/?$",
            r"^/api/auth/verify_token/?$",
            r"^/api/docs/?",
            r"^/api/schema/?",
            r"^/api/guide/?",
            r"^/api/developers/?",
            r"^/api/support/?",
            r"^/api/health/?$",
            r"^/api/payment/webhook/?$",  # For Moyasar webhook
            r"^/api/v1/openapi.json/?$",
        ]

        for pattern in exempt_paths:
            if re.match(pattern, request.path):
                return None

        # Check rate limiting
        if not self._check_rate_limit(request):
            return JsonResponse(
                {
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": self.RATE_LIMIT_WINDOW,
                },
                status=429,
            )

        # Check for token in Authorization header
        auth_header = request.headers.get("Authorization", "")

        # If no Authorization header, check for token in cookie
        if not auth_header and settings.JWT_COOKIE_NAME in request.COOKIES:
            token = request.COOKIES.get(settings.JWT_COOKIE_NAME)
            auth_header = f"Bearer {token}"

        if not auth_header.startswith("Bearer "):
            return JsonResponse(
                {"detail": "Authentication required. Please provide a valid Bearer token."},
                status=401,
            )

        token = auth_header.split(" ")[1]

        # Verify token
        user = TokenService.get_user_from_token(token)

        if not user:
            return JsonResponse({"detail": "Invalid or expired token."}, status=401)

        # Check if user is active
        if not user.is_active:
            return JsonResponse({"detail": "User account is disabled."}, status=401)

        # Set authenticated user on request
        request.user = user

        # Add token to request for potential use in services
        request.auth_token = token

        # Log the authentication
        logger.debug(f"Authenticated request for user {user.id} to {request.path}")

        return None

    def process_response(self, request, response):
        # Track authentication processing time for performance metrics
        if hasattr(request, "_auth_start_time"):
            auth_time = time.time() - request._auth_start_time
            # Only log if it took longer than 50ms
            if auth_time > 0.05:
                logger.warning(f"Auth middleware took {auth_time:.3f}s for {request.path}")

        return response

    def _check_rate_limit(self, request):
        """
        Check if the request should be rate limited.

        Args:
            request: The HTTP request

        Returns:
            bool: True if request should be allowed, False if rate limited
        """
        # Get client identifier (IP address or user ID if authenticated)
        client_id = request.META.get("REMOTE_ADDR")
        if hasattr(request, "user") and request.user.is_authenticated:
            client_id = f"user_{request.user.id}"

        # Get current timestamp
        now = datetime.now()

        # Get existing requests for this client
        cache_key = f"{self.RATE_LIMIT_CACHE_PREFIX}{client_id}"
        requests = cache.get(cache_key, [])

        # Remove old requests outside the window
        requests = [ts for ts in requests if now - ts < timedelta(seconds=self.RATE_LIMIT_WINDOW)]

        # Check if we're over the limit
        if len(requests) >= self.MAX_REQUESTS_PER_WINDOW:
            return False

        # Add current request
        requests.append(now)
        cache.set(cache_key, requests, self.RATE_LIMIT_WINDOW)

        return True
