"""
Error tracking and monitoring configuration for QueueMe backend
"""

import logging
import os

from django.conf import settings

logger = logging.getLogger("queueme")


def configure_sentry():
    """
    Configure Sentry for error tracking in production
    """
    if not os.environ.get("SENTRY_DSN"):
        logger.warning(
            "SENTRY_DSN environment variable not set. Error tracking will be limited to logs only."
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=os.environ.get("SENTRY_DSN"),
            integrations=[
                DjangoIntegration(),
                CeleryIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=0.2,
            send_default_pii=False,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=os.environ.get("SENTRY_RELEASE", "v1.0"),
            # Configure contexts that will be attached to all events
            before_send=before_send_event,
        )
        logger.info("Sentry error tracking configured successfully")
        return True
    except ImportError:
        logger.warning("Sentry SDK not installed. Install with: pip install sentry-sdk")
        return False
    except Exception as e:
        logger.error(f"Failed to configure Sentry: {str(e)}")
        return False


def before_send_event(event, hint):
    """
    Process events before sending to Sentry
    - Remove sensitive information
    - Add custom context
    """
    # Don't send certain errors
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        if isinstance(exc_value, (KeyboardInterrupt, SystemExit)):
            return None

    # Remove sensitive data
    if "request" in event and event["request"]:
        if "headers" in event["request"]:
            headers = event["request"]["headers"]
            # Remove authorization headers
            if "Authorization" in headers:
                headers["Authorization"] = "[FILTERED]"
            if "Cookie" in headers:
                headers["Cookie"] = "[FILTERED]"

    # Add custom context
    event["contexts"] = event.get("contexts", {})
    event["contexts"]["app"] = {
        "name": "QueueMe",
        "environment": os.environ.get("ENVIRONMENT", "production"),
        "version": os.environ.get("APP_VERSION", "v1.0"),
    }

    return event


def configure_prometheus():
    """
    Configure Prometheus metrics for monitoring
    """
    try:
        pass

        from prometheus_client import Counter, Histogram

        # Define global metrics
        REQUEST_COUNT = Counter(
            "queueme_request_count",
            "Total number of HTTP requests",
            ["method", "endpoint", "status"],
        )

        REQUEST_LATENCY = Histogram(
            "queueme_request_latency_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint"],
        )

        DB_QUERY_COUNT = Counter(
            "queueme_db_query_count",
            "Total number of database queries",
            ["model", "operation"],
        )

        DB_QUERY_LATENCY = Histogram(
            "queueme_db_query_latency_seconds",
            "Database query latency in seconds",
            ["model", "operation"],
        )

        CACHE_HIT_COUNT = Counter(
            "queueme_cache_hit_count", "Total number of cache hits", ["cache_name"]
        )

        CACHE_MISS_COUNT = Counter(
            "queueme_cache_miss_count", "Total number of cache misses", ["cache_name"]
        )

        # Export metrics
        logger.info("Prometheus metrics configured successfully")
        return {
            "REQUEST_COUNT": REQUEST_COUNT,
            "REQUEST_LATENCY": REQUEST_LATENCY,
            "DB_QUERY_COUNT": DB_QUERY_COUNT,
            "DB_QUERY_LATENCY": DB_QUERY_LATENCY,
            "CACHE_HIT_COUNT": CACHE_HIT_COUNT,
            "CACHE_MISS_COUNT": CACHE_MISS_COUNT,
        }
    except ImportError:
        logger.warning(
            "Prometheus client not installed. Install with: pip install prometheus-client"
        )
        return {}
    except Exception as e:
        logger.error(f"Failed to configure Prometheus: {str(e)}")
        return {}


def configure_logging():
    """
    Configure enhanced logging for the application
    """
    try:
        # Ensure log directory exists
        log_dir = os.path.join(settings.BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)

        # Configure logging
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "verbose": {
                        "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                        "style": "{",
                    },
                    "simple": {
                        "format": "{levelname} {message}",
                        "style": "{",
                    },
                    "json": {
                        "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s", "process": %(process)d, "thread": %(thread)d}',
                        "style": "%",
                    },
                },
                "filters": {
                    "require_debug_false": {
                        "()": "django.utils.log.RequireDebugFalse",
                    },
                    "require_debug_true": {
                        "()": "django.utils.log.RequireDebugTrue",
                    },
                },
                "handlers": {
                    "console": {
                        "level": "INFO",
                        "filters": ["require_debug_true"],
                        "class": "logging.StreamHandler",
                        "formatter": "simple",
                    },
                    "file": {
                        "level": "INFO",
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": os.path.join(log_dir, "queueme.log"),
                        "maxBytes": 10485760,  # 10MB
                        "backupCount": 10,
                        "formatter": "verbose",
                    },
                    "json_file": {
                        "level": "INFO",
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": os.path.join(log_dir, "queueme.json.log"),
                        "maxBytes": 10485760,  # 10MB
                        "backupCount": 10,
                        "formatter": "json",
                    },
                    "mail_admins": {
                        "level": "ERROR",
                        "filters": ["require_debug_false"],
                        "class": "django.utils.log.AdminEmailHandler",
                    },
                    "error_file": {
                        "level": "ERROR",
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": os.path.join(log_dir, "error.log"),
                        "maxBytes": 10485760,  # 10MB
                        "backupCount": 10,
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
                        "handlers": ["mail_admins", "error_file"],
                        "level": "ERROR",
                        "propagate": False,
                    },
                    "queueme": {
                        "handlers": ["console", "file", "json_file", "error_file"],
                        "level": "INFO",
                        "propagate": True,
                    },
                    "queueme.security": {
                        "handlers": [
                            "console",
                            "file",
                            "json_file",
                            "mail_admins",
                            "error_file",
                        ],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "queueme.payment": {
                        "handlers": ["console", "file", "json_file", "error_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
            }
        )

        logger.info("Enhanced logging configured successfully")
        return True
    except Exception as e:
        print(f"Failed to configure logging: {str(e)}")
        return False


def setup_monitoring():
    """
    Set up all monitoring and error tracking
    """
    results = {
        "sentry": configure_sentry(),
        "prometheus": bool(configure_prometheus()),
        "logging": configure_logging(),
    }

    success = all(results.values())
    if success:
        logger.info("All monitoring systems configured successfully")
    else:
        failed = [k for k, v in results.items() if not v]
        logger.warning(
            f"Some monitoring systems failed to configure: {', '.join(failed)}"
        )

    return results


if __name__ == "__main__":
    # When run directly, configure all monitoring
    setup_monitoring()
