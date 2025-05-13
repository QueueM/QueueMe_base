"""
Prometheus metrics for QueueMe application.
Provides metrics for monitoring key performance indicators across the platform.
"""

import time
from functools import wraps

from django.conf import settings
from prometheus_client import Counter, Gauge, Histogram, Summary

# ===== Application Metrics =====

# API request metrics
API_REQUESTS = Counter(
    "queueme_api_requests_total", "Total count of API requests", ["method", "endpoint", "status"]
)

API_REQUEST_LATENCY = Histogram(
    "queueme_api_request_duration_seconds",
    "API request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 30.0, 60.0),
)

# Database metrics
DB_QUERY_LATENCY = Histogram(
    "queueme_db_query_duration_seconds",
    "Database query latency in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

DB_CONNECTION_POOL = Gauge(
    "queueme_db_connection_pool_size", "Current database connection pool size", ["database"]
)

# ===== Business Metrics =====

# Queue metrics
QUEUE_SIZE = Gauge(
    "queueme_queue_size", "Current number of customers in queues", ["shop_id", "queue_id"]
)

QUEUE_WAIT_TIME = Histogram(
    "queueme_queue_wait_time_seconds",
    "Customer wait time in queue",
    ["shop_id", "queue_id"],
    buckets=(60, 300, 600, 900, 1800, 2700, 3600, 5400, 7200),
)

# Booking metrics
BOOKING_CREATED = Counter(
    "queueme_bookings_created_total", "Total count of bookings created", ["shop_id", "service_id"]
)

BOOKING_STATUS_CHANGED = Counter(
    "queueme_booking_status_changes_total",
    "Total count of booking status changes",
    ["shop_id", "service_id", "from_status", "to_status"],
)

# Payment metrics
PAYMENT_PROCESSED = Counter(
    "queueme_payments_processed_total",
    "Total count of payments processed",
    ["status", "wallet_type", "payment_method"],
)

PAYMENT_AMOUNT = Counter(
    "queueme_payment_amount_total",
    "Total payment amount processed in SAR",
    ["status", "wallet_type"],
)

# User metrics
USER_REGISTRATIONS = Counter(
    "queueme_user_registrations_total", "Total count of user registrations", ["user_type"]
)

ACTIVE_USERS = Gauge("queueme_active_users", "Number of active users", ["user_type"])

# Shop metrics
SHOP_COUNT = Gauge("queueme_shop_count", "Total number of shops", ["subscription_type"])

# ===== Infrastructure Metrics =====

# Cache metrics
CACHE_HITS = Counter("queueme_cache_hits_total", "Total count of cache hits", ["cache_name"])

CACHE_MISSES = Counter("queueme_cache_misses_total", "Total count of cache misses", ["cache_name"])

# Celery metrics
TASK_EXECUTIONS = Counter(
    "queueme_celery_task_executions_total",
    "Total count of executed Celery tasks",
    ["task_name", "status"],
)

TASK_EXECUTION_TIME = Histogram(
    "queueme_celery_task_execution_seconds",
    "Celery task execution time in seconds",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

TASK_QUEUE_SIZE = Gauge(
    "queueme_celery_queue_size", "Current size of Celery task queues", ["queue_name"]
)

# ===== Utility Functions =====


def time_request(view_func):
    """Decorator to measure API request latency."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        response = view_func(request, *args, **kwargs)

        # Get the endpoint name from view function
        if hasattr(view_func, "__name__"):
            endpoint = view_func.__name__
        else:
            endpoint = view_func.__class__.__name__

        duration = time.time() - start_time

        # Record metrics
        API_REQUESTS.labels(
            method=request.method, endpoint=endpoint, status=response.status_code
        ).inc()

        API_REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)

        return response

    return wrapper


def time_database_query(query_type):
    """Decorator to measure database query latency."""

    def decorator(query_func):
        @wraps(query_func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = query_func(*args, **kwargs)
            duration = time.time() - start_time

            # Record metrics
            DB_QUERY_LATENCY.labels(query_type=query_type).observe(duration)

            return result

        return wrapper

    return decorator


def time_task_execution(task_func):
    """Decorator to measure Celery task execution time."""

    @wraps(task_func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = task_func(*args, **kwargs)
            status = "success"
        except Exception as e:
            status = "failure"
            raise e
        finally:
            duration = time.time() - start_time

            # Record metrics
            task_name = task_func.__name__

            TASK_EXECUTIONS.labels(task_name=task_name, status=status).inc()

            TASK_EXECUTION_TIME.labels(task_name=task_name).observe(duration)

        return result

    return wrapper
