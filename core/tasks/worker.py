"""
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


def task_with_retries(max_retries=3, countdown=30, priority=None, **task_kwargs):
    """
    Decorator for creating tasks with retry logic.

    Args:
        max_retries (int): Maximum number of retries
        countdown (int): Seconds to wait between retries
        priority (int): Task priority (lower is higher priority)
        **task_kwargs: Additional task options

    Returns:
        callable: Decorated task function
    """

    def decorator(func):
        # Set task priority if specified
        if priority is not None:
            task_kwargs['priority'] = priority
            
        @shared_task(bind=True, max_retries=max_retries, **task_kwargs)
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                # Ensure database connection is healthy if needed
                if not getattr(self, 'skip_db_check', False):
                    ensure_database_connection()
                    
                return func(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    f"Task {self.name} failed, retrying ({self.request.retries}/{max_retries}): {exc}"
                )

                # Check if we've reached max retries
                if self.request.retries >= max_retries:
                    logger.error(
                        f"Task {self.name} failed after {max_retries} retries: {exc}"
                    )
                    raise

                # Calculate backoff
                backoff = countdown * (2**self.request.retries)

                # Retry with backoff
                raise self.retry(exc=exc, countdown=backoff)

        return wrapper

    return decorator


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
