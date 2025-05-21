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
    - Request latency by method, endpoint, and status code
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
            resolver_match = resolve(request.path)
            if getattr(resolver_match, "view_name", None):
                return resolver_match.view_name
            if getattr(resolver_match, "url_name", None):
                return resolver_match.url_name
            if hasattr(resolver_match, "func") and hasattr(resolver_match.func, "__name__"):
                return resolver_match.func.__name__
            return request.path_info
        except Resolver404:
            return request.path_info

    def __call__(self, request):
        # Skip excluded paths
        if self.should_exclude_path(request.path):
            return self.get_response(request)

        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        endpoint = self.get_endpoint_name(request)
        method = request.method
        status_code = str(response.status_code)  # must be string for prometheus_client

        # CORRECT: Use status_code as the label!
        API_REQUESTS.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        API_REQUEST_LATENCY.labels(method=method, endpoint=endpoint, status_code=status_code).observe(duration)

        return response
