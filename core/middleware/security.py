"""
Security middleware for QueueMe application.

These middlewares implement various security features to protect the application
from common web vulnerabilities and attacks.
"""

import logging
import re
import uuid

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class ContentSecurityPolicyMiddleware:
    """
    Middleware that adds Content-Security-Policy header to responses.

    This header helps prevent XSS attacks by restricting which resources can be loaded.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.nonce = None

    def __call__(self, request):
        # Generate a random nonce for each request
        self.nonce = uuid.uuid4().hex
        request.csp_nonce = self.nonce

        # Process the request
        response = self.get_response(request)

        # Don't apply CSP to admin or static files
        if request.path.startswith("/admin/") or request.path.startswith("/static/"):
            return response

        # Build CSP directives
        directives = {
            "default-src": "'self'",
            "script-src": f"'self' 'nonce-{self.nonce}' https://cdn.jsdelivr.net https://*.google-analytics.com https://*.googleapis.com",
            "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "img-src": "'self' data: https: blob:",
            "font-src": "'self' https://fonts.gstatic.com",
            "connect-src": "'self' https://*.googleapis.com https://*.google-analytics.com",
            "frame-src": "'self' https://*.moyasar.com",
            "object-src": "'none'",
            "base-uri": "'self'",
            "form-action": "'self'",
            "frame-ancestors": "'self'",
            "upgrade-insecure-requests": "",
        }

        # Build CSP header value
        csp_value = "; ".join([f"{key} {value}" for key, value in directives.items() if value])

        # Add CSP header to response
        response["Content-Security-Policy"] = csp_value

        return response


class XFrameOptionsMiddleware:
    """
    Middleware that sets X-Frame-Options header to prevent clickjacking.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Set X-Frame-Options header to deny framing by default
        response["X-Frame-Options"] = "DENY"

        return response


class StrictTransportSecurityMiddleware:
    """
    Middleware that sets Strict-Transport-Security header to enforce HTTPS.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only add HSTS header if HTTPS is enabled
        if settings.SECURE_SSL_REDIRECT:
            max_age = 31536000  # 1 year in seconds
            response["Strict-Transport-Security"] = f"max-age={max_age}; includeSubDomains; preload"

        return response


class ReferrerPolicyMiddleware:
    """
    Middleware that sets Referrer-Policy header to control referrer information.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Set Referrer-Policy header
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class XContentTypeOptionsMiddleware:
    """
    Middleware that sets X-Content-Type-Options header to prevent MIME type sniffing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Set X-Content-Type-Options header
        response["X-Content-Type-Options"] = "nosniff"

        return response


class PermissionsPolicyMiddleware:
    """
    Middleware that sets Permissions-Policy header to control browser features.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Set Permissions-Policy header
        # Restrict various potentially dangerous browser features
        permissions = {
            "accelerometer": "()",
            "camera": "()",
            "microphone": "()",
            "geolocation": "(self)",
            "payment": "(self)",
            "usb": "()",
            "gyroscope": "()",
            "magnetometer": "()",
            "midi": "()",
            "sync-xhr": "(self)",
            "autoplay": "(self)",
        }

        policy_value = ", ".join([f"{key}={value}" for key, value in permissions.items()])
        response["Permissions-Policy"] = policy_value

        return response


class SQLInjectionProtectionMiddleware:
    """
    Middleware that checks for potential SQL injection attacks.

    This is a basic protection layer that checks for typical SQL injection patterns
    in request parameters. It should be used in addition to proper ORM usage and
    parameterized queries.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Patterns that might indicate SQL injection attempts
        self.sql_patterns = [
            r"(\%27)|(\')|(--)|(\%23)|(#)",
            r"((\%3D)|(=))[^\n]*((\%27)|(\')|(--)|(\%3B)|(;))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%6F)|o|(\%4F))(\s|\+|\%20)*((\%72)|r|(\%52))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%6F)|o|(\%4F))(\s|\+|\%20)*((\%72)|r|(\%52))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%61)|a|(\%41))(\s|\+|\%20)*((\%6E)|n|(\%4E))(\s|\+|\%20)*((\%64)|d|(\%44))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%6F)|o|(\%4F))(\s|\+|\%20)*((\%72)|r|(\%52))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%75)|u|(\%55))(\s|\+|\%20)*((\%6E)|n|(\%4E))(\s|\+|\%20)*((\%69)|i|(\%49))(\s|\+|\%20)*((\%6F)|o|(\%4F))(\s|\+|\%20)*((\%6E)|n|(\%4E))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%73)|s|(\%53))(\s|\+|\%20)*((\%65)|e|(\%45))(\s|\+|\%20)*((\%6C)|l|(\%4C))(\s|\+|\%20)*((\%65)|e|(\%45))(\s|\+|\%20)*((\%63)|c|(\%43))(\s|\+|\%20)*((\%74)|t|(\%54))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%69)|i|(\%49))(\s|\+|\%20)*((\%6E)|n|(\%4E))(\s|\+|\%20)*((\%73)|s|(\%53))(\s|\+|\%20)*((\%65)|e|(\%45))(\s|\+|\%20)*((\%72)|r|(\%52))(\s|\+|\%20)*((\%74)|t|(\%54))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%64)|d|(\%44))(\s|\+|\%20)*((\%65)|e|(\%45))(\s|\+|\%20)*((\%6C)|l|(\%4C))(\s|\+|\%20)*((\%65)|e|(\%45))(\s|\+|\%20)*((\%74)|t|(\%54))(\s|\+|\%20)*((\%65)|e|(\%45))",
            r"((\%27)|(\'))(\s|\+|\%20)*((\%75)|u|(\%55))(\s|\+|\%20)*((\%70)|p|(\%50))(\s|\+|\%20)*((\%64)|d|(\%44))(\s|\+|\%20)*((\%61)|a|(\%41))(\s|\+|\%20)*((\%74)|t|(\%54))(\s|\+|\%20)*((\%65)|e|(\%45))",
        ]

        # Compile patterns for efficiency
        self.sql_patterns_compiled = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.sql_patterns
        ]

    def check_sql_injection(self, value):
        """Check if a string value contains SQL injection patterns"""
        if not isinstance(value, str):
            return False

        for pattern in self.sql_patterns_compiled:
            if pattern.search(value):
                return True
        return False

    def __call__(self, request):
        # Check GET parameters
        for key, value in request.GET.items():
            if self.check_sql_injection(value):
                logger.warning(f"Potential SQL injection detected in GET parameter: {key}={value}")
                return HttpResponseForbidden("Forbidden: Invalid request")

        # Check POST parameters (excluding file uploads)
        for key, value in request.POST.items():
            if self.check_sql_injection(value):
                logger.warning(f"Potential SQL injection detected in POST parameter: {key}={value}")
                return HttpResponseForbidden("Forbidden: Invalid request")

        return self.get_response(request)
