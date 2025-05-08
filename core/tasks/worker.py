"""
Task worker implementation for the Queue Me platform.

This module provides utilities for implementing Celery workers and tasks.
"""

import functools
import logging
import time

from celery import Task, shared_task
from celery.signals import task_failure, task_postrun, task_prerun, worker_ready
from django.db import connections

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """
    Base Celery task with common functionality.

    Features:
    - Automatic retry on specified exceptions
    - Performance monitoring
    - Database connection management
    - Error logging
    """

    # Automatically retry on these exceptions
    autoretry_for = (
        # Add specific exceptions here (e.g., RequestException, ConnectionError)
    )

    # Retry settings
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True

    def __call__(self, *args, **kwargs):
        """
        Execute task with timing and error handling.
        """
        start_time = time.time()

        try:
            # Close any stale database connections
            self._close_db_connections()

            # Execute task
            result = super().__call__(*args, **kwargs)

            # Log performance for slow tasks
            duration = time.time() - start_time
            if duration > 5:  # Log if task took more than 5 seconds
                logger.warning(
                    f"Slow task {self.name} completed in {duration:.2f}s "
                    f"(args: {args}, kwargs: {kwargs})"
                )
            elif duration > 1:  # Log if task took more than 1 second
                logger.info(f"Task {self.name} completed in {duration:.2f}s")

            return result

        except Exception as exc:
            # Log exception
            logger.exception(
                f"Task {self.name} failed: {exc} " f"(args: {args}, kwargs: {kwargs})"
            )
            raise

        finally:
            # Close database connections
            self._close_db_connections()

    def _close_db_connections(self):
        """Close database connections to prevent leaks."""
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Handle task failure.

        Args:
            exc: The exception
            task_id: Task ID
            args: Task arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        logger.error(
            f"Task {self.name}[{task_id}] failed: {exc} "
            f"(args: {args}, kwargs: {kwargs})"
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


def task_with_retries(max_retries=3, countdown=30, **task_kwargs):
    """
    Decorator for creating tasks with retry logic.

    Args:
        max_retries (int): Maximum number of retries
        countdown (int): Seconds to wait between retries
        **task_kwargs: Additional task options

    Returns:
        callable: Decorated task function
    """

    def decorator(func):
        @shared_task(bind=True, max_retries=max_retries, **task_kwargs)
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
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
def task_prerun_handler(task_id, task, *args, **kwargs):
    """
    Handle task pre-run signal.

    Args:
        task_id: Task ID
        task: Task instance
        *args: Signal arguments
        **kwargs: Signal keyword arguments
    """
    logger.debug(f"Starting task {task.name}[{task_id}]")


@task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    """
    Handle task post-run signal.

    Args:
        task_id: Task ID
        task: Task instance
        *args: Signal arguments
        **kwargs: Signal keyword arguments
    """
    logger.debug(f"Completed task {task.name}[{task_id}]")

    # Close database connections
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


@task_failure.connect
def task_failure_handler(task_id, exception, traceback, *args, **kwargs):
    """
    Handle task failure signal.

    Args:
        task_id: Task ID
        exception: The exception
        traceback: Exception traceback
        *args: Signal arguments
        **kwargs: Signal keyword arguments
    """
    logger.error(f"Task {task_id} failed: {exception}")

    # Close database connections
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


@worker_ready.connect
def worker_ready_handler(**kwargs):
    """
    Handle worker ready signal.

    Args:
        **kwargs: Signal keyword arguments
    """
    logger.info("Celery worker is ready")
