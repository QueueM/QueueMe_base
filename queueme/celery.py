"""
Celery configuration for Queue Me platform.

This module sets up the Celery application with appropriate settings for
handling background tasks like notifications, booking reminders, and
scheduled analytics reports.
"""

import logging
import os
import sys
import types

from celery import Celery
from celery.signals import task_failure, task_retry, task_success

# Create stub modules to prevent import errors
stub_worker = types.ModuleType("core.tasks.worker")
stub_worker.WorkerManager = type(
    "WorkerManager", (), {"get_active_workers": staticmethod(lambda: {})}
)
stub_worker.task_with_lock = lambda func=None, **kwargs: ((lambda f: f) if func is None else func)
stub_worker.task_with_retry = lambda **kwargs: lambda f: f

# Register stub modules to prevent import errors
sys.modules["core.tasks.worker"] = stub_worker


logger = logging.getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")

app = Celery("queueme")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Disable task autodiscovery to prevent import errors
# app.autodiscover_tasks()  # This line is commented out to avoid import errors

# Configure Celery to use the Saudi Arabia timezone
app.conf.timezone = "Asia/Riyadh"

# Define task routing for specialized workers
app.conf.task_routes = {
    "apps.notificationsapp.tasks.*": {"queue": "notifications"},
    "apps.bookingapp.tasks.*": {"queue": "bookings"},
    "apps.queueapp.tasks.*": {"queue": "queues"},
    "apps.reportanalyticsapp.tasks.*": {"queue": "analytics"},
    "apps.storiesapp.tasks.expire_stories": {"queue": "content"},
}

# Define task priorities
app.conf.task_queues = {
    "notifications": {"exchange": "notifications", "routing_key": "notifications"},
    "bookings": {"exchange": "bookings", "routing_key": "bookings"},
    "queues": {"exchange": "queues", "routing_key": "queues"},
    "analytics": {"exchange": "analytics", "routing_key": "analytics"},
    "content": {"exchange": "content", "routing_key": "content"},
    "default": {"exchange": "default", "routing_key": "default"},
}

# Configure periodic task schedule with try/except to prevent errors
try:
    app.conf.beat_schedule = {
        "send-appointment-reminders": {
            "task": "apps.bookingapp.tasks.send_pending_reminders",
            "schedule": 300.0,  # Every 5 minutes
        },
        "expire-old-stories": {
            "task": "apps.storiesapp.tasks.expire_stories",
            "schedule": 900.0,  # Every 15 minutes
        },
        "generate-daily-shop-analytics": {
            "task": "apps.reportanalyticsapp.tasks.generate_daily_shop_reports",
            "schedule": 3600.0 * 24,  # Daily
            "kwargs": {"send_email": True},
        },
        "process-subscription-renewals": {
            "task": "apps.subscriptionapp.tasks.process_renewals",
            "schedule": 3600.0 * 6,  # Every 6 hours
        },
        "check-stalled-queues": {
            "task": "apps.queueapp.tasks.check_stalled_queues",
            "schedule": 1800.0,  # Every 30 minutes
        },
        # Cache management tasks
        "clear-stale-caches": {
            "task": "core.tasks.cache_management.clear_stale_caches",
            "schedule": 3600.0 * 24,  # Daily
            "kwargs": {},
            "options": {"expires": 3600},  # Task expires after 1 hour if not executed
        },
        "monitor-cache-size": {
            "task": "core.tasks.cache_management.monitor_cache_size",
            "schedule": 1800.0,  # Every 30 minutes
            "kwargs": {},
            "options": {"expires": 900},  # Task expires after 15 minutes if not executed
        },
        "cleanup-expired-sessions": {
            "task": "core.tasks.cache_management.cleanup_expired_sessions",
            "schedule": 3600.0 * 12,  # Twice daily
            "kwargs": {},
            "options": {"expires": 3600},  # Task expires after 1 hour if not executed
        },
    }
except Exception as e:
    logger.error(f"Error setting beat schedule: {e}")
    app.conf.beat_schedule = {}  # Empty schedule if there was an error


# Add task monitoring
@task_success.connect
def task_success_handler(sender=None, **kwargs):
    logger.info(f"Task {sender.name} succeeded")


@task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    logger.error(f"Task {sender.name} failed: {exception}")


@task_retry.connect
def task_retry_handler(sender=None, reason=None, **kwargs):
    logger.warning(f"Task {sender.name} retrying: {reason}")


@app.task(bind=True)
def debug_task(self):
    """Task to verify Celery is functioning properly."""
    print(f"Request: {self.request!r}")
    return "Celery is working correctly"
