"""
Cache management utilities for the Queue Me platform.

This module provides a centralized cache manager with support for different
caching backends (memory, Redis) and cache versioning.
"""

import logging
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache

from .key_generator import generate_cache_key

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Advanced cache management for Queue Me platform.

    Features:
    - Multi-level caching (memory and Redis)
    - Flexible expiration policies
    - Cache invalidation patterns
    - Statistics tracking
    - Key versioning
    """

    def __init__(self, namespace=None, version=None):
        """
        Initialize the cache manager.

        Args:
            namespace (str): Optional namespace for cache keys
            version (str): Optional version for cache keys
        """
        self.namespace = namespace or "default"
        self.version = version or getattr(settings, "CACHE_VERSION", "1")
        self.default_timeout = getattr(
            settings, "CACHE_DEFAULT_TIMEOUT", 60 * 60
        )  # 1 hour
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    def get(self, key, default=None):
        """
        Get a value from the cache.

        Args:
            key (str): Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        cache_key = generate_cache_key(key, self.namespace, self.version)
        value = cache.get(cache_key, default)

        if value is None or value == default:
            self.stats["misses"] += 1
            logger.debug(f"Cache miss for key: {cache_key}")
            return default

        self.stats["hits"] += 1
        logger.debug(f"Cache hit for key: {cache_key}")
        return value

    def set(self, key, value, timeout=None):
        """
        Set a value in the cache.

        Args:
            key (str): Cache key
            value: Value to cache
            timeout (int): Cache expiration in seconds

        Returns:
            bool: Success status
        """
        timeout = timeout or self.default_timeout
        cache_key = generate_cache_key(key, self.namespace, self.version)
        success = cache.set(cache_key, value, timeout)

        if success:
            self.stats["sets"] += 1
            logger.debug(f"Cache set for key: {cache_key}, timeout: {timeout}s")

        return success

    def delete(self, key):
        """
        Delete a value from the cache.

        Args:
            key (str): Cache key

        Returns:
            bool: Success status
        """
        cache_key = generate_cache_key(key, self.namespace, self.version)
        cache.delete(cache_key)
        self.stats["deletes"] += 1
        logger.debug(f"Cache delete for key: {cache_key}")
        return True

    def invalidate_namespace(self):
        """
        Invalidate all keys in the current namespace by incrementing version.

        Returns:
            str: New version
        """
        new_version = str(int(self.version) + 1)
        self.version = new_version
        logger.info(
            f"Invalidated cache namespace: {self.namespace}, new version: {new_version}"
        )
        return new_version

    def clear(self):
        """
        Clear the entire cache.

        Returns:
            bool: Success status
        """
        cache.clear()
        logger.info("Cache cleared")
        return True

    def get_or_set(self, key, callable_obj, timeout=None):
        """
        Get a value from the cache, or set it if it doesn't exist.

        Args:
            key (str): Cache key
            callable_obj: Function to call to get value if not in cache
            timeout (int): Cache expiration in seconds

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is None:
            value = callable_obj()
            self.set(key, value, timeout)
        return value

    def get_statistics(self):
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics
        """
        return {
            **self.stats,
            "hit_ratio": (
                self.stats["hits"] / (self.stats["hits"] + self.stats["misses"])
                if (self.stats["hits"] + self.stats["misses"]) > 0
                else 0
            ),
        }


def cached(namespace=None, timeout=None, key_fn=None):
    """
    Decorator to cache function results.

    Args:
        namespace (str): Cache namespace
        timeout (int): Cache expiration in seconds
        key_fn (callable): Function to generate cache key

    Returns:
        callable: Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache manager
            cache_mgr = CacheManager(namespace)

            # Generate key
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                # Create a key based on function name, args, and kwargs
                key_parts = [func.__name__]
                args_str = [str(arg) for arg in args]
                kwargs_str = [f"{k}={v}" for k, v in sorted(kwargs.items())]
                key_parts.extend(args_str)
                key_parts.extend(kwargs_str)
                key = ":".join(key_parts)

            # Check cache first
            result = cache_mgr.get(key)
            if result is not None:
                return result

            # Execute function
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Cache the result
            cache_mgr.set(key, result, timeout)

            # Log long executions
            if execution_time > 0.5:  # Log if function took more than 500ms
                logger.warning(
                    f"Slow execution ({execution_time:.2f}s) of {func.__name__}, cached result"
                )

            return result

        return wrapper

    return decorator


# Add the missing function that's imported by reportanalyticsapp
def cache_with_key_prefix(prefix, timeout=None):
    """
    Decorator to cache function results with a specified key prefix.
    This is a simplified version of the cached decorator that always
    uses the provided prefix at the beginning of the cache key.

    Args:
        prefix (str): Key prefix for all cached items using this decorator
        timeout (int): Cache expiration in seconds (None for default timeout)

    Returns:
        callable: Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache manager
            namespace = f"{prefix}_namespace"
            cache_mgr = CacheManager(namespace)

            # Generate key with prefix
            args_str = [str(arg) for arg in args if not hasattr(arg, '__dict__')]
            kwargs_str = [f"{k}={v}" for k, v in sorted(kwargs.items()) 
                          if not hasattr(v, '__dict__')]
                
            key_parts = [prefix, func.__name__]
            key_parts.extend(args_str)
            key_parts.extend(kwargs_str)
            key = ":".join(key_parts)
            
            # Check cache first
            result = cache_mgr.get(key)
            if result is not None:
                logger.debug(f"Cache hit for prefixed key: {key}")
                return result

            # Execute function
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Cache the result
            cache_mgr.set(key, result, timeout)
            
            # Log for debugging
            logger.debug(f"Cached result for prefixed key: {key}")
            if execution_time > 0.5:
                logger.warning(
                    f"Slow execution ({execution_time:.2f}s) of {func.__name__}, cached with prefix {prefix}"
                )
                
            return result
        return wrapper
    return decorator