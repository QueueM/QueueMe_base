"""
Task worker implementation for the Queue Me platform.

This module provides utilities for implementing Celery workers and tasks.
"""

import functools
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Type

try:
    from celery import Task, shared_task
    from celery.signals import (
        task_failure,
        task_postrun,
        task_prerun,
        worker_process_init,
        worker_ready,
    )
    from django.db import OperationalError, connection, connections, transaction
    from django.db.models import Max

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

try:
    from core.monitoring.metrics import (
        DB_CONNECTION_ERRORS_TOTAL,
        TASK_DURATION_SECONDS,
        TASK_FAILURES_TOTAL,
        TASK_RETRIES_TOTAL,
    )
except ImportError:
    # Create dummy classes if monitoring not available
    class DummyMetric:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    TASK_DURATION_SECONDS = DummyMetric()
    TASK_FAILURES_TOTAL = DummyMetric()
    TASK_RETRIES_TOTAL = DummyMetric()
    DB_CONNECTION_ERRORS_TOTAL = DummyMetric()

logger = logging.getLogger(__name__)

# Thread-local storage for database connection state
_thread_local = threading.local()


class WorkerManager:
    """
    Manager for Celery worker operations.

    This class provides utilities for managing worker processes,
    connection pools, and monitoring worker status.
    """

    @staticmethod
    def get_active_workers():
        """Get list of active worker processes."""
        try:
            if CELERY_AVAILABLE:
                from celery.app.control import Control

                try:
                    from queueme.celery import app

                    control = Control(app)
                    return control.inspect().active()
                except BaseException:
                    pass
        except BaseException:
            pass
        return {}


def task_with_lock(func=None, lock_timeout=60, lock_id=None):
    """
    Decorator for creating tasks with distributed locks.

    Args:
        func: Function to decorate
        lock_timeout: Lock timeout in seconds
        lock_id: Custom lock ID (defaults to task name)

    Returns:
        Decorated function that acquires a lock before execution
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Skip lock logic if disabled
            if os.environ.get("DISABLE_CELERY") == "True":
                return f(*args, **kwargs)

            try:
                # Default lock ID uses function name
                task_id = lock_id or f.__name__

                # Acquire lock
                try:
                    from django_redis import get_redis_connection

                    redis = get_redis_connection("default")
                    lock_acquired = redis.set(f"task_lock:{task_id}", 1, ex=lock_timeout, nx=True)

                    if not lock_acquired:
                        logger.warning(f"Task {task_id} is already running, skipping execution")
                        return None

                    try:
                        # Execute the task
                        return f(*args, **kwargs)
                    finally:
                        # Release lock
                        redis.delete(f"task_lock:{task_id}")
                except BaseException:
                    # If Redis fails, still execute the task
                    return f(*args, **kwargs)
            except BaseException:
                # If anything fails, still execute the task
                return f(*args, **kwargs)

        return wrapper

    # Handle both @task_with_lock and @task_with_lock()
    if func is None:
        return decorator
    return decorator(func)


def task_with_retry(max_retries=3, backoff=2, max_backoff=3600):
    """
    Decorator for tasks with exponential backoff retries.

    Args:
        max_retries: Maximum retry attempts
        backoff: Backoff multiplier
        max_backoff: Maximum backoff in seconds

    Returns:
        Decorated function with retry logic
    """

    def decorator(func):
        if not CELERY_AVAILABLE or os.environ.get("DISABLE_CELERY") == "True":
            return func

        try:

            @shared_task(bind=True, max_retries=max_retries)
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    # Calculate backoff with exponential increase
                    retry_count = self.request.retries
                    retry_delay = min(backoff**retry_count, max_backoff)

                    logger.warning(f"Task {self.name} failed, retrying in {retry_delay}s: {exc}")

                    raise self.retry(exc=exc, countdown=retry_delay)

            return wrapper
        except BaseException:
            # Fallback implementation (just run the function)
            return func

    return decorator


def ensure_database_connection():
    """
    Ensure database connection is established and healthy.
    Close and reopen if needed to prevent stale connections.
    """
    try:
        # Check if we've verified the connection in this thread recently
        current_time = time.time()
        last_check_time = getattr(_thread_local, "db_check_time", 0)

        # Only check every 5 minutes to avoid overhead
        if current_time - last_check_time < 300:  # 5 minutes
            return True

        # Test the connection
        connection.ensure_connection()

        # Update the last check time
        _thread_local.db_check_time = current_time
        return True
    except Exception:
        # Handle OperationalError and other exceptions
        logger.warning("Database connection is stale, reconnecting...")

        try:
            for conn in connections.all():
                if conn.connection:
                    conn.close()

            # Attempt to establish a new connection
            connection.connect()
            _thread_local.db_check_time = time.time()
            logger.info("Database reconnection successful")
            return True
        except Exception:
            try:
                DB_CONNECTION_ERRORS_TOTAL.inc()
            except BaseException:
                pass
            logger.error("Failed to reconnect to database")
            return False
