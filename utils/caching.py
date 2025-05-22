"""
Caching utilities and decorators for Queue Me platform.

This module provides decorators and utilities for caching class properties,
function results, and implementing intelligent cache invalidation strategies.
"""

import functools
from datetime import timedelta
from typing import Callable, List, Optional

from django.core.cache import cache
from django.db.models import Model
from django.utils import timezone

from .cache_manager import CacheManager, cache_key_builder


class cached_property:
    """
    A decorator that converts a method with a single self argument into a
    property cached on the instance.

    Similar to Django's cached_property but with optional timeout support.
    """

    def __init__(self, func: Callable, timeout: Optional[int] = None):
        self.func = func
        self.timeout = timeout
        functools.update_wrapper(self, func)

    def __get__(self, instance, cls=None):
        if instance is None:
            return self

        cache_key = f"_cached_prop_{self.func.__name__}"

        # Check if value is already cached in instance
        if hasattr(instance, cache_key):
            cached_data = getattr(instance, cache_key)

            # If there's a timeout, check if it's expired
            if self.timeout is not None:
                timestamp, value = cached_data
                if timezone.now() < timestamp + timedelta(seconds=self.timeout):
                    return value
            else:
                # No timeout, just return the cached value
                return cached_data

        # Calculate fresh value
        value = self.func(instance)

        # Cache the value on the instance
        if self.timeout is not None:
            setattr(instance, cache_key, (timezone.now(), value))
        else:
            setattr(instance, cache_key, value)

        return value


def cache_result(
    timeout: int = 300,
    key_args: Optional[List[str]] = None,
    key_kwargs: Optional[List[str]] = None,
    prefix: Optional[str] = None,
):
    """
    Decorator to cache function results.

    Args:
        timeout: Cache timeout in seconds
        key_args: List of positional argument indices to include in cache key
        key_kwargs: List of keyword argument names to include in cache key
        prefix: Optional cache key prefix

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_args = []

            # Include specified positional args in key
            if key_args:
                for idx in key_args:
                    if idx < len(args):
                        cache_args.append(args[idx])

            # Include specified keyword args in key
            cache_kwargs = {}
            if key_kwargs:
                for name in key_kwargs:
                    if name in kwargs:
                        cache_kwargs[name] = kwargs[name]

            # If no specific args/kwargs specified, use all of them
            if not key_args and not key_kwargs:
                cache_args = args
                cache_kwargs = kwargs

            # Create the cache key
            key_prefix = prefix or f"{func.__module__}.{func.__qualname__}"
            cache_key = cache_key_builder(
                *cache_args, prefix=key_prefix, **cache_kwargs
            )

            # Try to get cached result
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Calculate and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


def invalidate_cache(key_pattern: str):
    """
    Decorator to invalidate cache entries matching a pattern after function execution.

    Args:
        key_pattern: Cache key pattern to invalidate

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the function
            result = func(*args, **kwargs)

            # Invalidate matching cache entries
            cache_manager = CacheManager()
            cache_manager.invalidate_pattern(key_pattern)

            return result

        return wrapper

    return decorator


def model_cache_key(model_instance: Model, prefix: Optional[str] = None) -> str:
    """
    Generate a cache key for a model instance.

    Args:
        model_instance: Django model instance
        prefix: Optional prefix

    Returns:
        Cache key string
    """
    model_class = model_instance.__class__
    app_label = model_class._meta.app_label
    model_name = model_class._meta.model_name
    pk = model_instance.pk

    if prefix:
        return f"{prefix}:{app_label}:{model_name}:{pk}"
    else:
        return f"{app_label}:{model_name}:{pk}"


def calculate_cache_timeout(base_timeout: int = 300, dynamic: bool = False) -> int:
    """
    Calculate cache timeout value, optionally with some randomness to prevent
    cache stampede.

    Args:
        base_timeout: Base timeout in seconds
        dynamic: Whether to add randomness

    Returns:
        Calculated timeout
    """
    import random

    if dynamic:
        # Add ±10% randomness
        variation = base_timeout * 0.1
        return int(base_timeout + random.uniform(-variation, variation))
    else:
        return base_timeout
