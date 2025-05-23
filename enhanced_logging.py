"""
Enhanced Logging Configuration for QueueMe Backend

This module implements a comprehensive logging configuration for the QueueMe backend,
providing structured logging, error tracking, and performance monitoring for
production observability and reliability.

The logging configuration includes:
1. Structured JSON logging for machine readability
2. Different log levels for development and production
3. Separate handlers for different log types (error, info, debug)
4. Request ID tracking for distributed tracing
5. Performance logging for slow queries and operations
"""

import os
import time
import uuid
from functools import wraps

import structlog
from django.conf import settings
from django.db import connection
from django.utils.deprecation import MiddlewareMixin

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Base logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(settings.BASE_DIR, "logs/queueme.log"),
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(settings.BASE_DIR, "logs/error.log"),
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
        },
        "performance_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(settings.BASE_DIR, "logs/performance.log"),
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 5,
            "formatter": "json",
        },
        "security_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(settings.BASE_DIR, "logs/security.log"),
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file", "mail_admins"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["error_file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["security_file", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["performance_file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.performance": {
            "handlers": ["performance_file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.security": {
            "handlers": ["security_file", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.payment": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.booking": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "queueme.auth": {
            "handlers": ["console", "file", "error_file", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Get loggers
logger = structlog.get_logger("queueme")
performance_logger = structlog.get_logger("queueme.performance")
security_logger = structlog.get_logger("queueme.security")
payment_logger = structlog.get_logger("queueme.payment")
booking_logger = structlog.get_logger("queueme.booking")
auth_logger = structlog.get_logger("queueme.auth")


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware to add a request ID to each request for tracing.

    This middleware adds a unique request ID to each request, which is then
    included in all log messages related to that request. This allows for
    distributed tracing and correlation of log messages across services.
    """

    def process_request(self, request):
        """
        Process the request and add a request ID.

        Args:
            request: HTTP request
        """
        request_id = str(uuid.uuid4())
        request.id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)

    def process_response(self, request, response):
        """
        Process the response and add the request ID header.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            HTTP response with request ID header
        """
        if hasattr(request, "id"):
            response["X-Request-ID"] = request.id
        structlog.contextvars.clear_contextvars()
        return response


class PerformanceLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log request performance metrics.

    This middleware logs the time taken to process each request, as well as
    the number of database queries executed during the request.
    """

    def process_request(self, request):
        """
        Process the request and record the start time.

        Args:
            request: HTTP request
        """
        request.start_time = time.time()
        request.query_count_start = len(connection.queries)

    def process_response(self, request, response):
        """
        Process the response and log performance metrics.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            HTTP response
        """
        if hasattr(request, "start_time"):
            # Calculate request duration
            duration = time.time() - request.start_time

            # Calculate query count
            query_count = len(connection.queries) - getattr(
                request, "query_count_start", 0
            )

            # Log performance metrics
            performance_logger.info(
                "request_performance",
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=int(duration * 1000),
                query_count=query_count,
            )

            # Add performance headers
            response["X-Request-Duration-MS"] = str(int(duration * 1000))
            response["X-Query-Count"] = str(query_count)

            # Log slow requests (> 500ms)
            if duration > 0.5:
                performance_logger.warning(
                    "slow_request",
                    path=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    duration_ms=int(duration * 1000),
                    query_count=query_count,
                )

        return response


def log_function_call(func=None, *, level="info", logger_name="queueme"):
    """
    Decorator to log function calls with arguments and return values.

    Args:
        func: Function to decorate
        level: Log level (default: 'info')
        logger_name: Logger name (default: 'queueme')

    Returns:
        Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger
            log = structlog.get_logger(logger_name)
            log_method = getattr(log, level)

            # Log function call
            log_method(
                "function_call",
                function=func.__name__,
                module=func.__module__,
                args=str(args),
                kwargs=str(kwargs),
            )

            # Call function
            try:
                result = func(*args, **kwargs)

                # Log function return
                log_method(
                    "function_return",
                    function=func.__name__,
                    module=func.__module__,
                    result=str(result)[:100],  # Truncate long results
                )

                return result
            except Exception as e:
                # Log function error
                log.error(
                    "function_error",
                    function=func.__name__,
                    module=func.__module__,
                    error=str(e),
                    exc_info=True,
                )
                raise

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def log_payment_event(event_type, payment_id, amount=None, status=None, **kwargs):
    """
    Log a payment event.

    Args:
        event_type: Type of payment event
        payment_id: Payment ID
        amount: Payment amount
        status: Payment status
        **kwargs: Additional event data
    """
    payment_logger.info(
        event_type,
        payment_id=payment_id,
        amount=amount,
        status=status,
        **kwargs,
    )


def log_security_event(event_type, user_id=None, ip_address=None, **kwargs):
    """
    Log a security event.

    Args:
        event_type: Type of security event
        user_id: User ID
        ip_address: IP address
        **kwargs: Additional event data
    """
    security_logger.info(
        event_type,
        user_id=user_id,
        ip_address=ip_address,
        **kwargs,
    )


def log_booking_event(event_type, booking_id, user_id=None, shop_id=None, **kwargs):
    """
    Log a booking event.

    Args:
        event_type: Type of booking event
        booking_id: Booking ID
        user_id: User ID
        shop_id: Shop ID
        **kwargs: Additional event data
    """
    booking_logger.info(
        event_type,
        booking_id=booking_id,
        user_id=user_id,
        shop_id=shop_id,
        **kwargs,
    )


def log_auth_event(event_type, user_id=None, ip_address=None, **kwargs):
    """
    Log an authentication event.

    Args:
        event_type: Type of authentication event
        user_id: User ID
        ip_address: IP address
        **kwargs: Additional event data
    """
    auth_logger.info(
        event_type,
        user_id=user_id,
        ip_address=ip_address,
        **kwargs,
    )


def log_slow_query(query, duration_ms, params=None):
    """
    Log a slow database query.

    Args:
        query: SQL query
        duration_ms: Query duration in milliseconds
        params: Query parameters
    """
    performance_logger.warning(
        "slow_query",
        query=query,
        duration_ms=duration_ms,
        params=str(params),
    )


def log_cache_event(event_type, cache_key, hit=None, **kwargs):
    """
    Log a cache event.

    Args:
        event_type: Type of cache event
        cache_key: Cache key
        hit: Whether the cache was hit
        **kwargs: Additional event data
    """
    performance_logger.info(
        event_type,
        cache_key=cache_key,
        hit=hit,
        **kwargs,
    )


def apply_logging_config(django_settings):
    """
    Apply logging configuration to Django settings.

    Args:
        django_settings: Django settings module
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(django_settings.BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Set logging configuration
    django_settings.LOGGING = LOGGING_CONFIG

    # Add middleware
    middleware = django_settings.MIDDLEWARE

    # Add RequestIDMiddleware at the beginning
    if "queueme.logging.RequestIDMiddleware" not in middleware:
        middleware.insert(0, "queueme.logging.RequestIDMiddleware")

    # Add PerformanceLoggingMiddleware after RequestIDMiddleware
    if "queueme.logging.PerformanceLoggingMiddleware" not in middleware:
        middleware.insert(1, "queueme.logging.PerformanceLoggingMiddleware")

    django_settings.MIDDLEWARE = middleware

    return django_settings


# Example usage
"""
# Example 1: Logging a function call
@log_function_call(level='info', logger_name='queueme.booking')
def create_appointment(user_id, service_id, start_time):
    # Function implementation
    # ...
    return appointment

# Example 2: Logging a payment event
def process_payment(payment_id, amount):
    # Process payment
    # ...
    log_payment_event(
        'payment_processed',
        payment_id=payment_id,
        amount=amount,
        status='success',
        payment_method='credit_card',
    )
    return payment

# Example 3: Logging a security event
def login_user(request, user):
    # Login user
    # ...
    log_security_event(
        'user_login',
        user_id=user.id,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT'),
    )
    return response

# Example 4: Logging a slow query
def log_slow_queries():
    for query in connection.queries:
        if float(query['time']) > 0.1:  # 100ms
            log_slow_query(
                query=query['sql'],
                duration_ms=float(query['time']) * 1000,
                params=query.get('params'),
            )
"""
