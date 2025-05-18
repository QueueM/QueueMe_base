"""
Task scheduling utilities for the Queue Me platform.

This module provides utilities for scheduling tasks using Celery.
"""

import logging
from datetime import datetime, timedelta
from functools import wraps

from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone

logger = logging.getLogger(__name__)


# Convenience wrapper function
def schedule_task(task_func, args=None, kwargs=None, countdown=None, eta=None):
    """Simple wrapper for TaskScheduler.schedule_task method."""
    return TaskScheduler.schedule_task(task_func, args, kwargs, countdown, eta)


def recurring_task(schedule, name=None, args=None, kwargs=None):
    """
    Decorator to create a recurring task.

    Args:
        schedule: Celery schedule (crontab, timedelta, etc.)
        name (str): Task name (defaults to function name)
        args (list): Task arguments
        kwargs (dict): Task keyword arguments

    Returns:
        function: Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        task_name = name or f"{func.__module__}.{func.__name__}"
        TaskScheduler.create_periodic_task(
            name=task_name, task_func=func, schedule=schedule, args=args, kwargs=kwargs
        )
        return wrapper

    return decorator


class TaskScheduler:
    """
    Task scheduling utilities for Queue Me.

    This class provides methods to schedule both one-time and recurring tasks.
    """

    @staticmethod
    def schedule_task(task_func, args=None, kwargs=None, countdown=None, eta=None):
        """
        Schedule a one-time task.

        Args:
            task_func: Celery task function
            args (list): Task arguments
            kwargs (dict): Task keyword arguments
            countdown (int): Seconds to wait before executing
            eta (datetime): Specific time to execute

        Returns:
            celery.result.AsyncResult: Task result
        """
        args = args or []
        kwargs = kwargs or {}

        # Schedule task
        if eta:
            result = task_func.apply_async(args=args, kwargs=kwargs, eta=eta)
            logger.info(f"Scheduled task {task_func.__name__} for {eta}")
        elif countdown:
            result = task_func.apply_async(args=args, kwargs=kwargs, countdown=countdown)
            logger.info(f"Scheduled task {task_func.__name__} in {countdown} seconds")
        else:
            result = task_func.apply_async(args=args, kwargs=kwargs)
            logger.info(f"Scheduled task {task_func.__name__} immediately")

        return result

    @staticmethod
    def schedule_task_at_time(
        task_func, hour, minute, args=None, kwargs=None, day=None, month=None
    ):
        """
        Schedule a task for a specific time.

        Args:
            task_func: Celery task function
            hour (int): Hour (0-23)
            minute (int): Minute (0-59)
            args (list): Task arguments
            kwargs (dict): Task keyword arguments
            day (int): Day of month (1-31)
            month (int): Month (1-12)

        Returns:
            celery.result.AsyncResult: Task result
        """
        args = args or []
        kwargs = kwargs or {}

        # Calculate execution time
        now = timezone.now()
        if day and month:
            # Specific day and month
            target_dt = datetime(now.year, month, day, hour, minute, tzinfo=now.tzinfo)
        elif day:
            # Specific day of current month
            target_dt = datetime(now.year, now.month, day, hour, minute, tzinfo=now.tzinfo)
        else:
            # Today at the specified time
            target_dt = datetime(now.year, now.month, now.day, hour, minute, tzinfo=now.tzinfo)

        # If target time is in the past, move to next day/month/year
        if target_dt < now:
            if day and month:
                # Move to next year
                target_dt = datetime(now.year + 1, month, day, hour, minute, tzinfo=now.tzinfo)
            elif day:
                # Move to next month
                if now.month == 12:
                    target_dt = datetime(now.year + 1, 1, day, hour, minute, tzinfo=now.tzinfo)
                else:
                    target_dt = datetime(
                        now.year, now.month + 1, day, hour, minute, tzinfo=now.tzinfo
                    )
            else:
                # Move to next day
                target_dt = target_dt + timedelta(days=1)

        # Schedule task
        result = task_func.apply_async(args=args, kwargs=kwargs, eta=target_dt)
        logger.info(f"Scheduled task {task_func.__name__} for {target_dt}")

        return result

    @staticmethod
    def create_periodic_task(name, task_func, schedule, args=None, kwargs=None):
        """
        Create a periodic task using celery beat.

        Note: This requires proper celery beat setup.

        Args:
            name (str): Task name
            task_func: Celery task function
            schedule: Celery schedule (crontab, timedelta, etc.)
            args (list): Task arguments
            kwargs (dict): Task keyword arguments

        Returns:
            PeriodicTask: Created periodic task
        """
        import json

        from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

        args = args or []
        kwargs = kwargs or {}

        # Create schedule
        if isinstance(schedule, crontab):
            # Create crontab schedule
            crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=schedule._orig_minute,
                hour=schedule._orig_hour,
                day_of_week=schedule._orig_day_of_week,
                day_of_month=schedule._orig_day_of_month,
                month_of_year=schedule._orig_month_of_year,
            )

            # Create or update periodic task
            task, created = PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    "task": task_func.name,
                    "crontab": crontab_schedule,
                    "args": json.dumps(args),
                    "kwargs": json.dumps(kwargs),
                    "enabled": True,
                },
            )
        else:
            # Assume it's an interval
            if isinstance(schedule, timedelta):
                seconds = schedule.total_seconds()
                minutes, seconds = divmod(seconds, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)

                if days:
                    interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                        every=int(days), period="days"
                    )
                elif hours:
                    interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                        every=int(hours), period="hours"
                    )
                elif minutes:
                    interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                        every=int(minutes), period="minutes"
                    )
                else:
                    interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                        every=int(seconds), period="seconds"
                    )
            else:
                # Assume it's already a number of seconds
                interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                    every=int(schedule), period="seconds"
                )

            # Create or update periodic task
            task, created = PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    "task": task_func.name,
                    "interval": interval_schedule,
                    "args": json.dumps(args),
                    "kwargs": json.dumps(kwargs),
                    "enabled": True,
                },
            )

        action = "Created" if created else "Updated"
        logger.info(f"{action} periodic task '{name}'")

        return task

    @staticmethod
    def disable_periodic_task(name):
        """
        Disable a periodic task.

        Args:
            name (str): Task name

        Returns:
            bool: Success status
        """
        from django_celery_beat.models import PeriodicTask

        try:
            task = PeriodicTask.objects.get(name=name)
            task.enabled = False
            task.save()
            logger.info(f"Disabled periodic task '{name}'")
            return True
        except PeriodicTask.DoesNotExist:
            logger.warning(f"Periodic task '{name}' not found")
            return False

    @staticmethod
    def enable_periodic_task(name):
        """
        Enable a periodic task.

        Args:
            name (str): Task name

        Returns:
            bool: Success status
        """
        from django_celery_beat.models import PeriodicTask

        try:
            task = PeriodicTask.objects.get(name=name)
            task.enabled = True
            task.save()
            logger.info(f"Enabled periodic task '{name}'")
            return True
        except PeriodicTask.DoesNotExist:
            logger.warning(f"Periodic task '{name}' not found")
            return False

    @staticmethod
    def delete_periodic_task(name):
        """
        Delete a periodic task.

        Args:
            name (str): Task name

        Returns:
            bool: Success status
        """
        from django_celery_beat.models import PeriodicTask

        try:
            task = PeriodicTask.objects.get(name=name)
            task.delete()
            logger.info(f"Deleted periodic task '{name}'")
            return True
        except PeriodicTask.DoesNotExist:
            logger.warning(f"Periodic task '{name}' not found")
            return False


@shared_task
def schedule_task_in_future(task_name, args=None, kwargs=None, countdown=None, eta=None):
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
