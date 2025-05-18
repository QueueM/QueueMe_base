"""
Tasks module initialization.

This file ensures tasks are properly registered and available.
"""

from django.conf import settings

# Import worker manager functionality if not in disabled mode
if not getattr(settings, "DISABLE_CELERY", False):
    try:
        from .worker import WorkerManager, task_with_lock, task_with_retry

        __all__ = ["WorkerManager", "task_with_lock", "task_with_retry"]
    except ImportError:
        # Create dummy implementations if imports fail
        class WorkerManager:
            @staticmethod
            def get_active_workers():
                return {}

        def task_with_lock(func=None, **kwargs):
            if func is None:
                return lambda f: f
            return func

        def task_with_retry(**kwargs):
            return lambda f: f

        __all__ = ["WorkerManager", "task_with_lock", "task_with_retry"]
else:
    # Create dummy implementations when Celery is disabled
    class WorkerManager:
        @staticmethod
        def get_active_workers():
            return {}

    def task_with_lock(func=None, **kwargs):
        if func is None:
            return lambda f: f
        return func

    def task_with_retry(**kwargs):
        return lambda f: f

    __all__ = ["WorkerManager", "task_with_lock", "task_with_retry"]

# Make these directly importable from core.tasks
WorkerManager
task_with_lock
task_with_retry
