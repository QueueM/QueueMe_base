"""
Middleware for automatically capturing metrics for all HTTP requests.
"""

import re
import time

from django.urls import Resolver404, resolve

from core.monitoring.metrics import API_REQUEST_LATENCY, API_REQUESTS


class PrometheusMetricsMiddleware:
    """
    Middleware that captures request metrics and records them to Prometheus.

    This middleware tracks:
    - Request counts by method, endpoint, and status code
    - Request latency by method and endpoint
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Patterns to exclude from metrics (like static files, health checks)
        self.exclude_patterns = [
            r"^/static/",
            r"^/media/",
            r"^/favicon\.ico$",
            r"^/health/",
            r"^/metrics/",
        ]

    def should_exclude_path(self, path):
        """Check if path should be excluded from metrics"""
        for pattern in self.exclude_patterns:
            if re.match(pattern, path):
                return True
        return False

    def get_endpoint_name(self, request):
        """Extract the view name or URL pattern from the request"""
        try:
            # Try to resolve the URL to get the view name
            resolver_match = resolve(request.path)
            if hasattr(resolver_match, "view_name") and resolver_match.view_name:
                return resolver_match.view_name

            # Fall back to URL name if view_name is not available
            if hasattr(resolver_match, "url_name") and resolver_match.url_name:
                return resolver_match.url_name

            # If neither is available, use the view function name
            if hasattr(resolver_match, "func") and hasattr(resolver_match.func, "__name__"):
                return resolver_match.func.__name__

            # Last resort: use the URL pattern
            return request.path_info
        except Resolver404:
            # If URL resolution fails, use the path
            return request.path_info

    def __call__(self, request):
        # Skip excluded paths
        if self.should_exclude_path(request.path):
            return self.get_response(request)

        # Start timing
        start_time = time.time()

        # Process the request
        response = self.get_response(request)

        # Calculate request duration
        duration = time.time() - start_time

        # Get endpoint name
        endpoint = self.get_endpoint_name(request)

        # Record metrics
        API_REQUESTS.labels(
            method=request.method, endpoint=endpoint, status=response.status_code
        ).inc()

        API_REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)

        return response
