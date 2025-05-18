#!/usr/bin/env python3

# Create a clean version of the worker.py file
clean_worker_code = '''"""
Task worker implementation for the Queue Me platform.

This module provides utilities for implementing Celery workers and tasks.
"""

import functools
import logging
import time
import threading
import os
from typing import Any, Dict, Optional, Type, Callable, List

from celery import Task, shared_task
from celery.signals import task_failure, task_postrun, task_prerun, worker_ready, worker_process_init
from django.db import connections, transaction, OperationalError, connection
from django.db.models import Max
from prometheus_client import Counter, Histogram

from core.monitoring.metrics import (
    TASK_DURATION_SECONDS,
    TASK_FAILURES_TOTAL,
    TASK_RETRIES_TOTAL,
    DB_CONNECTION_ERRORS_TOTAL,
)

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
        from celery.app.control import Control
        from queueme.celery import app

        control = Control(app)
        return control.inspect().active()


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
            # Default lock ID uses function name
            task_id = lock_id or f.__name__

            # Acquire lock
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
        @shared_task(bind=True, max_retries=max_retries)
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Calculate backoff with exponential increase
                retry_count = self.request.retries
                retry_delay = min(backoff ** retry_count, max_backoff)

                logger.warning(
                    f"Task {self.name} failed, retrying in {retry_delay}s: {exc}"
                )

                raise self.retry(exc=exc, countdown=retry_delay)

        return wrapper

    return decorator


def ensure_database_connection():
    """
    Ensure database connection is established and healthy.
    Close and reopen if needed to prevent stale connections.
    """
    try:
        # Check if we've verified the connection in this thread recently
        current_time = time.time()
        last_check_time = getattr(_thread_local, 'db_check_time', 0)

        # Only check every 5 minutes to avoid overhead
        if current_time - last_check_time < 300:  # 5 minutes
            return True

        # Test the connection
        connection.ensure_connection()

        # Update the last check time
        _thread_local.db_check_time = current_time
        return True
    except OperationalError:
        # Connection is broken, close and retry
        logger.warning("Database connection is stale, reconnecting...")

        for conn in connections.all():
            if conn.connection:
                conn.close()

        try:
            # Attempt to establish a new connection
            connection.connect()
            _thread_local.db_check_time = time.time()
            logger.info("Database reconnection successful")
            return True
        except Exception as e:
            DB_CONNECTION_ERRORS_TOTAL.inc()
            logger.error(f"Failed to reconnect to database: {str(e)}")
            return False


class BaseTask(Task):
    """
    Base Celery task with enhanced performance monitoring and error handling.

    Features:
    - Automatic retry on specified exceptions
    - Performance monitoring with Prometheus metrics
    - Database connection management
    - Error logging and tracking
    - Transaction management
    """

    # Automatically retry on these exceptions
    autoretry_for = (
        OperationalError,  # Database operational errors
        ConnectionError,   # Network connection errors
        TimeoutError,      # Timeouts
        Exception,         # Generic exceptions as fallback
    )

    # Retry settings
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True

    # Performance thresholds (in seconds)
    WARNING_THRESHOLD = 1.0
    ERROR_THRESHOLD = 5.0

    # Transaction isolation level
    # Options: 'read_committed', 'repeatable_read', 'serializable'
    transaction_isolation_level = 'read_committed'

    # Default task priority (lower means higher priority)
    priority = 5

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute task with enhanced monitoring and error handling.
        """
        start_time = time.time()
        task_id = self.request.id if self.request else None
        worker_pid = os.getpid()

        try:
            # Ensure database connection is healthy
            if not ensure_database_connection():
                raise OperationalError("Could not establish database connection")

            # Set transaction isolation level if specified
            if self.transaction_isolation_level:
                self._set_transaction_isolation_level()

            # Execute task within transaction
            with transaction.atomic():
                result = super().__call__(*args, **kwargs)

            # Record task duration
            duration = time.time() - start_time
            TASK_DURATION_SECONDS.labels(
                task_name=self.name,
                status="success"
            ).observe(duration)

            # Log performance metrics
            if duration > self.ERROR_THRESHOLD:
                logger.error(
                    f"Task {self.name}[{task_id}] took {duration:.2f}s "
                    f"(Worker: {worker_pid}, args: {args}, kwargs: {kwargs})"
                )
            elif duration > self.WARNING_THRESHOLD:
                logger.warning(
                    f"Task {self.name}[{task_id}] took {duration:.2f}s "
                    f"(Worker: {worker_pid})"
                )
            else:
                logger.debug(
                    f"Task {self.name}[{task_id}] completed in {duration:.2f}s "
                    f"(Worker: {worker_pid})"
                )

            return result

        except Exception as exc:
            # Record failure
            TASK_FAILURES_TOTAL.labels(
                task_name=self.name,
                error_type=exc.__class__.__name__
            ).inc()

            # Log exception
            logger.exception(
                f"Task {self.name}[{task_id}] failed: {exc} "
                f"(Worker: {worker_pid}, args: {args}, kwargs: {kwargs})"
            )
            raise

        finally:
            # Close database connections
            self._close_db_connections(force=False)

    def _set_transaction_isolation_level(self) -> None:
        """Set database transaction isolation level."""
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {self.transaction_isolation_level.replace('_', ' ')}")
                elif connection.vendor == 'mysql':
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {self.transaction_isolation_level.replace('_', ' ')}")
                # SQLite doesn't support explicit isolation level setting
        except Exception as e:
            logger.warning(f"Failed to set transaction isolation level: {str(e)}")

    def _close_db_connections(self, force: bool = False) -> None:
        """
        Close database connections to prevent leaks.

        Args:
            force: If True, close even if connection appears healthy
        """
        try:
            for conn in connections.all():
                if conn.connection is not None:
                    if force:
                        conn.close()
                    else:
                        conn.close_if_unusable_or_obsolete()
        except Exception as e:
            DB_CONNECTION_ERRORS_TOTAL.inc()
            logger.error(f"Error closing database connection: {str(e)}")

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """
        Handle task failure with enhanced error tracking.

        Args:
            exc: The exception
            task_id: Task ID
            args: Task arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        # Record failure
        TASK_FAILURES_TOTAL.labels(
            task_name=self.name,
            error_type=exc.__class__.__name__
        ).inc()

        # Log error
        logger.error(
            f"Task {self.name}[{task_id}] failed: {exc} "
            f"(Worker: {os.getpid()}, args: {args}, kwargs: {kwargs})"
        )

        # Force close database connections after failure
        self._close_db_connections(force=True)

        # Call parent implementation
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """
        Handle task retry with enhanced tracking.

        Args:
            exc: The exception
            task_id: Task ID
            args: Task arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        # Record retry
        TASK_RETRIES_TOTAL.labels(
            task_name=self.name,
            error_type=exc.__class__.__name__
        ).inc()

        # Log retry
        logger.warning(
            f"Task {self.name}[{task_id}] retrying: {exc} "
            f"(Worker: {os.getpid()}, args: {args}, kwargs: {kwargs})"
        )

        # Force close database connections before retry
        self._close_db_connections(force=True)

        # Call parent implementation
        super().on_retry(exc, task_id, args, kwargs, einfo)


class TransactionalTask(BaseTask):
    """Task that guarantees atomic transaction execution."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        with transaction.atomic():
            return super().__call__(*args, **kwargs)


class DatabaselessTask(BaseTask):
    """Task that doesn't require database access."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Skip DB connection checks
        return super(BaseTask, self).__call__(*args, **kwargs)


@task_prerun.connect
def task_prerun_handler(task_id: str, task: Task, *args: Any, **kwargs: Any) -> None:
    """Handle task pre-run events."""
    logger.debug(f"Starting task {task.name}[{task_id}] on worker {os.getpid()}")


@task_postrun.connect
def task_postrun_handler(task_id: str, task: Task, *args: Any, **kwargs: Any) -> None:
    """Handle task post-run events."""
    logger.debug(f"Completed task {task.name}[{task_id}] on worker {os.getpid()}")

    # Close database connections
    for conn in connections.all():
        if conn.connection is not None:
            conn.close_if_unusable_or_obsolete()


@task_failure.connect
def task_failure_handler(task_id: str, exception: Exception, *args: Any, **kwargs: Any) -> None:
    """Handle task failure events."""
    logger.error(f"Task {task_id} failed: {str(exception)}")

    # Force close database connections after failure
    for conn in connections.all():
        if conn.connection is not None:
            conn.close()


@worker_ready.connect
def worker_ready_handler(*args: Any, **kwargs: Any) -> None:
    """Handle worker ready events."""
    worker_pid = os.getpid()
    logger.info(f"Worker {worker_pid} is ready to process tasks")


@worker_process_init.connect
def worker_process_init_handler(*args: Any, **kwargs: Any) -> None:
    """
    Initialize worker process.

    Called when worker process starts, before any tasks are processed.
    """
    worker_pid = os.getpid()
    logger.info(f"Worker process {worker_pid} initializing")

    # Ensure all database connections are fresh at worker startup
    for conn in connections.all():
        if conn.connection is not None:
            conn.close()


@shared_task
def schedule_task_in_future(
    task_name, args=None, kwargs=None, countdown=None, eta=None
):
    """
    Meta-task to schedule another task in the future.

    This is useful when you want to schedule a task from a place
    where Celery is not directly accessible.

    Args:
        task_name (str): Full task name (e.g., 'app.tasks.my_task')
        args (list): Task arguments
        kwargs (dict): Task keyword arguments
        countdown (int): Seconds to wait before executing
        eta (str): ISO-formatted datetime string

    Returns:
        str: Task ID
    """
    args = args or []
    kwargs = kwargs or {}

    # Import task dynamically
    module_name, task_name = task_name.rsplit(".", 1)
    module = __import__(module_name, fromlist=[task_name])
    task = getattr(module, task_name)

    # Convert eta to datetime if provided
    if eta and isinstance(eta, str):
        from datetime import datetime
        eta = datetime.fromisoformat(eta)

    # Schedule task
    if eta:
        result = task.apply_async(args=args, kwargs=kwargs, eta=eta)
    elif countdown:
        result = task.apply_async(args=args, kwargs=kwargs, countdown=countdown)
    else:
        result = task.apply_async(args=args, kwargs=kwargs)

    logger.info(f"Scheduled task {task_name} with ID {result.id}")
    return result.id
'''

# Write the script to replace worker.py
with open("/tmp/replace_worker.py", "w") as f:
    f.write(
        '''#!/usr/bin/env python3
import os

# Clean file content
worker_code = """%s"""

# Replace worker.py with clean version
with open('/home/arise/queueme/core/tasks/worker.py', 'w') as f:
    f.write(worker_code)

print("Successfully replaced worker.py with clean version")
'''
        % clean_worker_code
    )

print("Created replacement script at /tmp/replace_worker.py")
print("Upload and run on server with:")
print(
    "scp /tmp/replace_worker.py arise@148.72.244.135:/tmp/ && ssh arise@148.72.244.135 'sudo python3 /tmp/replace_worker.py'"
)
