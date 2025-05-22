"""
Performance Monitoring Middleware

Middleware for monitoring request performance, database queries, and resource usage.
"""

import logging
import os
import re
import time
from typing import Any, Dict

import psutil
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from core.monitoring.database_performance import (
    get_slow_query_report,
    start_query_timer,
    stop_query_timer,
)

logger = logging.getLogger(__name__)

# Paths to exclude from detailed monitoring
DEFAULT_EXCLUDE_PATHS = [
    r"^/static/",
    r"^/media/",
    r"^/admin/jsi18n/",
    r"^/favicon\.ico$",
]

# Process for memory usage monitoring
_process = psutil.Process(os.getpid())


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware for monitoring request performance.

    Tracks:
    - Overall request time
    - Database query performance
    - Memory usage
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response
        self.enabled = getattr(settings, "PERFORMANCE_MONITORING", settings.DEBUG)
        self.slow_request_threshold = getattr(
            settings, "SLOW_REQUEST_THRESHOLD", 1.0
        )  # seconds

        # Paths to exclude from detailed monitoring
        exclude_paths = getattr(
            settings, "PERFORMANCE_EXCLUDE_PATHS", DEFAULT_EXCLUDE_PATHS
        )
        self.exclude_patterns = [re.compile(pattern) for pattern in exclude_paths]

        # Statistics tracking
        self.requests_processed = 0
        self.slow_requests = 0

        logger.info(
            f"Performance monitoring middleware {'enabled' if self.enabled else 'disabled'}"
        )

    def should_monitor(self, request) -> bool:
        """Determine if this request should be monitored."""
        if not self.enabled:
            return False

        # Skip monitoring for excluded paths
        path = request.path
        for pattern in self.exclude_patterns:
            if pattern.match(path):
                return False

        return True

    def process_request(self, request):
        """Process incoming request and start performance tracking."""
        request.start_time = time.time()

        if self.should_monitor(request):
            # Track memory before request
            request.start_memory = _process.memory_info().rss / 1024 / 1024  # MB

            # Start tracking database queries
            start_query_timer()

    def process_response(self, request, response):
        """Process the response and log performance metrics."""
        # Skip if start_time wasn't set (middleware not executed on request)
        if not hasattr(request, "start_time"):
            return response

        # Calculate request time
        request_time = time.time() - request.start_time

        # Check if we're monitoring this request
        if self.should_monitor(request):
            # Collect database query stats
            db_stats = stop_query_timer()

            # Calculate memory usage
            if hasattr(request, "start_memory"):
                end_memory = _process.memory_info().rss / 1024 / 1024  # MB
                memory_diff = end_memory - request.start_memory
            else:
                memory_diff = 0

            # Update stats
            self.requests_processed += 1

            # Check if request was slow
            is_slow = request_time > self.slow_request_threshold
            if is_slow:
                self.slow_requests += 1

                # Log detailed info for slow requests
                query_info = ""
                if db_stats and db_stats["query_count"] > 0:
                    query_info = f" | DB: {db_stats['query_count']} queries in {db_stats['query_time']:.3f}s"
                    if db_stats["slow_queries"]:
                        slow_count = len(db_stats["slow_queries"])
                        slow_time = db_stats["total_slow_query_time"]
                        query_info += (
                            f", {slow_count} slow queries taking {slow_time:.3f}s"
                        )

                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {request_time:.3f}s with status {response.status_code}{query_info}"
                )

                # Add server timing header for debugging
                response["Server-Timing"] = (
                    f"total;dur={request_time*1000:.0f},"
                    f"db;dur={db_stats['query_time']*1000:.0f}"
                )

            # Log basic info for all monitored requests
            log_level = logging.WARNING if is_slow else logging.DEBUG
            logger.log(
                log_level,
                f"Request: {request.method} {request.path} | "
                f"Time: {request_time:.3f}s | "
                f"Status: {response.status_code} | "
                f"Memory: {memory_diff:+.2f}MB",
            )

        return response

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics collected by the middleware."""
        return {
            "requests_processed": self.requests_processed,
            "slow_requests": self.slow_requests,
            "slow_percentage": (
                (self.slow_requests / self.requests_processed * 100)
                if self.requests_processed > 0
                else 0
            ),
            "slow_queries": get_slow_query_report(limit=10),
        }
