# Useful decorators
import functools
import time

from django.core.cache import cache
from django.db import transaction


def timed_execution(func):
    """Decorator to measure function execution time"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        print(f"{func.__name__} executed in {execution_time:.4f} seconds")
        return result

    return wrapper


def cached_result(timeout=300):
    """Cache function results for specified timeout"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = "cached_" + "_".join(key_parts)

            # Try to get cached result
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Calculate and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


def atomic_transaction(func):
    """Ensure function runs in a database transaction"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    return wrapper
