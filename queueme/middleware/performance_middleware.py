"""
Performance middleware for Queue Me platform.

This middleware tracks request processing time, logs slow requests,
and adds performance metrics to the response for monitoring.
"""

import json
import logging
import threading
import time

import psutil
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)
performance_logger = logging.getLogger("queueme.performance")

# Thread-local storage for request tracking
_thread_locals = threading.local()


class PerformanceMiddleware(MiddlewareMixin):
    """
    Middleware to track and log performance metrics.

    Monitors request processing time, memory usage, and other performance metrics.
    Logs slow requests and adds performance headers to the response.
    """

    def process_request(self, request):
        """Start timing the request"""
        _thread_locals.start_time = time.time()
        _thread_locals.sql_queries_count = 0

        # Track memory usage for potentially expensive requests
        if (
            settings.DEBUG
            or request.path.startswith("/api/reports/")
            or request.path.startswith("/api/analytics/")
        ):
            _thread_locals.start_memory = (
                psutil.Process().memory_info().rss / 1024 / 1024
            )  # MB

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Store the view name for logging purposes"""
        _thread_locals.view_name = view_func.__module__ + "." + view_func.__name__
        return None

    def _get_sql_count(self):
        """Get the number of SQL queries executed during the request"""
        # Use connection.queries if debug is enabled, otherwise use cached count
        from django.db import connection

        if settings.DEBUG:
            return len(connection.queries)
        return getattr(_thread_locals, "sql_queries_count", 0)

    def process_response(self, request, response):
        """Calculate and log request time, add performance headers"""
        if not hasattr(_thread_locals, "start_time"):
            return response

        # Calculate processing time
        total_time = time.time() - _thread_locals.start_time

        # Get view name if available
        view_name = getattr(_thread_locals, "view_name", "unknown_view")

        # Add performance headers if not a file/streaming response
        if hasattr(response, "headers"):
            response["X-Processing-Time"] = str(round(total_time * 1000)) + "ms"

            # Add SQL query count if DEBUG mode is enabled
            if settings.DEBUG:
                response["X-SQL-Queries"] = str(self._get_sql_count())

        # Log slow requests (> 1 second)
        if total_time > 1.0:
            memory_usage = ""
            if hasattr(_thread_locals, "start_memory"):
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                memory_diff = end_memory - _thread_locals.start_memory
                memory_usage = f", Memory: {memory_diff:.2f}MB"

            logger.warning(
                f"Slow request: {request.method} {request.path} took {total_time:.2f}s "
                f"(View: {view_name}, SQL: {self._get_sql_count()}{memory_usage})"
            )

            # Extra-detailed logging for extremely slow requests
            if total_time > 3.0:
                # Log detailed info for investigation
                user_id = getattr(request.user, "id", "anonymous")
                request_data = {}

                if request.method in ("POST", "PUT", "PATCH"):
                    try:
                        request_data = json.loads(request.body.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        request_data = "Unable to decode body"

                query_params = dict(request.GET.items())
                performance_logger.warning(
                    f"Very slow request details:\n"
                    f"  Path: {request.path}\n"
                    f"  Method: {request.method}\n"
                    f"  User: {user_id}\n"
                    f"  View: {view_name}\n"
                    f"  Processing Time: {total_time:.2f}s\n"
                    f"  SQL Queries: {self._get_sql_count()}\n"
                    f"  Query Params: {query_params}\n"
                    f"  Request Data: {request_data}"
                )

        # Make the memory available for garbage collection
        for attr in ("start_time", "sql_queries_count", "view_name", "start_memory"):
            if hasattr(_thread_locals, attr):
                delattr(_thread_locals, attr)

        return response
