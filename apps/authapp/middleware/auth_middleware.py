import logging
import re

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.authapp.services.token_service import TokenService

logger = logging.getLogger(__name__)


class AuthMiddleware(MiddlewareMixin):
    """
    Middleware for JWT authentication.
    """

    def process_request(self, request):
        """
        Process each request and verify JWT token if necessary.
        """
        # Skip authentication for excluded paths
        exempt_paths = [
            r"^/admin/",
            r"^/api/auth/request-otp/?$",
            r"^/api/auth/verify-otp/?$",
            r"^/api/auth/token/refresh/?$",
            r"^/api/auth/login/?$",
            r"^/api/docs/?",
            r"^/api/schema/?",
            r"^/api/guide/?",
            r"^/api/developers/?",
            r"^/api/support/?",
            r"^/static/",
            r"^/media/",
        ]

        # Check if path is exempt
        for pattern in exempt_paths:
            if re.match(pattern, request.path):
                return None

        # Skip authentication for non-API endpoints
        if not request.path.startswith("/api/"):
            return None

        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return JsonResponse({"detail": "Authentication credentials not provided."}, status=401)

        token = auth_header.split(" ")[1]

        # Verify token and get user
        user = TokenService.get_user_from_token(token)

        if not user:
            return JsonResponse({"detail": "Invalid or expired token."}, status=401)

        # Check if user is active
        if not user.is_active:
            return JsonResponse({"detail": "User account is disabled."}, status=401)

        # Set authenticated user on request
        request.user = user

        return None
