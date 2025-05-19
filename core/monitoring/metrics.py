"""
Prometheus metrics configuration for monitoring application performance.

This module defines custom metrics for monitoring queue activity, API performance,
database query times, and other crucial metrics for QueueMe.
"""

import time
from functools import wraps

from django.conf import settings
from django.db import connection
from prometheus_client import Counter, Gauge, Histogram

# ===========================================================
# API Metrics
# ===========================================================

# Histogram for API response times
API_REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds",
    "API request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# Counter for API requests
API_REQUESTS_TOTAL = Counter(
    "api_requests_total", "Total count of API requests", ["method", "endpoint", "status_code"]
)

# Add an alias for API_REQUESTS to fix middleware import error
API_REQUESTS = API_REQUESTS_TOTAL

# Counter for API errors
API_ERRORS_TOTAL = Counter(
    "api_errors_total", "Total count of API errors", ["method", "endpoint", "error_type"]
)

# ===========================================================
# Queue Metrics
# ===========================================================

# Gauge for current queue lengths by shop
QUEUE_LENGTH = Gauge(
    "queue_length", "Current number of customers in queue", ["shop_id", "queue_id", "status"]
)

# Histogram for customer wait times
CUSTOMER_WAIT_TIME = Histogram(
    "customer_wait_time_minutes",
    "Customer wait time in minutes",
    ["shop_id", "service_type"],
    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120),
)

# Counter for queue operations
QUEUE_OPERATIONS = Counter(
    "queue_operations_total",
    "Total count of queue operations",
    ["operation", "shop_id", "queue_id"],
)

# ===========================================================
# Database Metrics
# ===========================================================

# Histogram for database query times
DB_QUERY_LATENCY = Histogram(
    "db_query_latency_seconds",
    "Database query latency in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Counter for database query counts
DB_QUERIES_TOTAL = Counter("db_queries_total", "Total count of database queries", ["query_type"])

# Gauge for database connection pool
DB_CONNECTIONS = Gauge(
    "db_connections", "Current number of database connections", ["state"]  # active, idle
)

# ===========================================================
# Cache Metrics
# ===========================================================

# Counter for cache operations
CACHE_OPERATIONS = Counter(
    "cache_operations_total",
    "Total count of cache operations",
    ["operation", "status"],  # get/set/delete, hit/miss
)

# Histogram for cache operation latency
CACHE_OPERATION_LATENCY = Histogram(
    "cache_operation_latency_seconds",
    "Cache operation latency in seconds",
    ["operation"],
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

# ===========================================================
# Utility Decorators
# ===========================================================


def track_api_request(view_func):
    """
    Decorator to track API request metrics.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()

        # Call the view function
        response = view_func(request, *args, **kwargs)

        # Record metrics
        duration = time.time() - start_time
        method = request.method

        # Extract endpoint path, removing query parameters
        endpoint = request.path.split("?")[0]
        status_code = response.status_code

        # Update metrics
        API_REQUEST_LATENCY.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).observe(duration)

        API_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

        # Track errors separately
        if 400 <= status_code < 600:
            error_type = "client_error" if status_code < 500 else "server_error"
            API_ERRORS_TOTAL.labels(method=method, endpoint=endpoint, error_type=error_type).inc()

        return response

    return wrapper


def track_db_query(func):
    """
    Decorator to track database query metrics.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        # Call the function
        result = func(*args, **kwargs)

        # Record metrics
        duration = time.time() - start_time

        # Try to determine query type from function name
        func_name = func.__name__
        if "get" in func_name.lower():
            query_type = "select"
        elif any(op in func_name.lower() for op in ["create", "add", "insert"]):
            query_type = "insert"
        elif any(op in func_name.lower() for op in ["update", "change", "modify"]):
            query_type = "update"
        elif any(op in func_name.lower() for op in ["delete", "remove"]):
            query_type = "delete"
        else:
            query_type = "other"

        # Update metrics
        DB_QUERY_LATENCY.labels(query_type=query_type).observe(duration)
        DB_QUERIES_TOTAL.labels(query_type=query_type).inc()

        return result

    return wrapper


def track_cache_operation(operation):
    """
    Decorator factory to track cache operation metrics.

    Args:
        operation: The cache operation name (get, set, delete)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Call the cache function
            result = func(*args, **kwargs)

            # Record metrics
            duration = time.time() - start_time

            # For 'get' operations, track cache hits/misses
            status = "unknown"
            if operation == "get":
                status = "hit" if result is not None else "miss"
            else:
                status = "success"

            # Update metrics
            CACHE_OPERATIONS.labels(operation=operation, status=status).inc()
            CACHE_OPERATION_LATENCY.labels(operation=operation).observe(duration)

            return result

        return wrapper

    return decorator


def update_queue_metrics(shop_id, queue_id, length, status="waiting"):
    """
    Update queue length metrics.

    Args:
        shop_id: ID of the shop
        queue_id: ID of the queue
        length: Current queue length
        status: Queue status
    """
    QUEUE_LENGTH.labels(shop_id=str(shop_id), queue_id=str(queue_id), status=status).set(length)


def record_customer_wait_time(shop_id, service_type, wait_time_minutes):
    """
    Record customer wait time.

    Args:
        shop_id: ID of the shop
        service_type: Type of service
        wait_time_minutes: Wait time in minutes
    """
    CUSTOMER_WAIT_TIME.labels(shop_id=str(shop_id), service_type=service_type).observe(
        wait_time_minutes
    )


def record_queue_operation(operation, shop_id, queue_id):
    """
    Record a queue operation.

    Args:
        operation: Operation name (join, leave, call, serve, etc.)
        shop_id: ID of the shop
        queue_id: ID of the queue
    """
    QUEUE_OPERATIONS.labels(operation=operation, shop_id=str(shop_id), queue_id=str(queue_id)).inc()


def update_db_connection_metrics():
    """
    Update database connection metrics.
    """
    if hasattr(connection, "connection") and connection.connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active = cursor.fetchone()[0]

                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'")
                idle = cursor.fetchone()[0]

                DB_CONNECTIONS.labels(state="active").set(active)
                DB_CONNECTIONS.labels(state="idle").set(idle)
        except Exception:
            # Silently fail if we can't get connection stats
            pass