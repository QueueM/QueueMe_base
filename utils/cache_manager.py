"""
Cache management utilities for Queue Me platform.

This module provides tools for working with Django's cache framework,
including cache key generation, invalidation strategies, and specialized
cache managers for different data types.
"""

import hashlib
import json
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache


def cache_key_builder(*args, prefix: str = None, **kwargs) -> str:
    """
    Build a consistent cache key from a mix of arguments.

    Args:
        *args: Positional arguments to include in the key
        prefix: Optional prefix for the key
        **kwargs: Keyword arguments to include in the key

    Returns:
        A consistent cache key string
    """
    if prefix is None:
        prefix = "queueme"

    # Convert args and kwargs to a consistent string representation
    key_parts = [prefix]

    # Add args to key parts
    for arg in args:
        if isinstance(arg, (list, dict, set, tuple)):
            # Convert complex types to a string representation
            key_parts.append(
                hashlib.sha256(
                    json.dumps(arg, sort_keys=True).encode(), usedforsecurity=False
                ).hexdigest()
            )
        else:
            key_parts.append(str(arg))

    # Add sorted kwargs to ensure consistent key generation
    if kwargs:
        sorted_items = sorted(kwargs.items())
        for k, v in sorted_items:
            if isinstance(v, (list, dict, set, tuple)):
                key_parts.append(
                    f"{k}:{hashlib.sha256(json.dumps(v, sort_keys=True).encode(),usedforsecurity=False).hexdigest()}"
                )
            else:
                key_parts.append(f"{k}:{v}")

    # Join all parts with a delimiter and create the final key
    return ":".join(key_parts)


class CacheManager:
    """
    Advanced cache manager for the Queue Me platform.

    Provides methods for getting, setting, and invalidating cache with
    support for versioning, namespaces, and intelligent invalidation strategies.
    """

    def __init__(self, namespace: str = "queueme", version: int = 1):
        """
        Initialize a cache manager with a namespace and version.

        Args:
            namespace: Namespace for cache keys, defaults to "queueme"
            version: Cache version, defaults to 1
        """
        self.namespace = namespace
        self.version = version
        self.default_timeout = getattr(
            settings, "CACHE_TIMEOUT", 300
        )  # 5 minutes by default

    def build_key(self, key: str) -> str:
        """
        Build a namespaced and versioned cache key.

        Args:
            key: Original cache key

        Returns:
            Fully qualified cache key
        """
        return f"{self.namespace}:v{self.version}:{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Default value if key doesn't exist

        Returns:
            Cached value or default
        """
        return cache.get(self.build_key(key), default)

    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds, uses default if None
        """
        if timeout is None:
            timeout = self.default_timeout

        cache.set(self.build_key(key), value, timeout)

    def delete(self, key: str) -> None:
        """
        Delete a value from the cache.

        Args:
            key: Cache key
        """
        cache.delete(self.build_key(key))

    def get_or_set(
        self, key: str, default_func: Callable, timeout: Optional[int] = None
    ) -> Any:
        """
        Get a value from the cache or set it with the result of default_func.

        Args:
            key: Cache key
            default_func: Function to call to get default value
            timeout: Cache timeout in seconds

        Returns:
            Cached or computed value
        """
        if timeout is None:
            timeout = self.default_timeout

        return cache.get_or_set(self.build_key(key), default_func, timeout)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        This is a more advanced feature that uses wildcards to delete
        multiple cache keys at once. Note that this requires a cache backend
        that supports pattern-based deletion.

        Args:
            pattern: Pattern to match cache keys

        Returns:
            Number of keys invalidated
        """
        # This implementation assumes a Redis backend with scan_iter
        try:
            from django_redis import get_redis_connection

            conn = get_redis_connection("default")
            pattern_key = self.build_key(f"{pattern}*")
            count = 0

            for key in conn.scan_iter(match=pattern_key):
                conn.delete(key)
                count += 1

            return count
        except ImportError:
            # Fallback for non-Redis backends
            return 0

    def invalidate_by_tags(self, *tags: str) -> None:
        """
        Invalidate cache by tags.

        This method invalidates all cache entries associated with any of the
        given tags.

        Args:
            *tags: Tag strings
        """
        for tag in tags:
            self.invalidate_pattern(f"tag:{tag}")

    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment an integer value in the cache.

        Args:
            key: Cache key
            amount: Amount to increment

        Returns:
            New value
        """
        return cache.incr(self.build_key(key), amount)

    def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement an integer value in the cache.

        Args:
            key: Cache key
            amount: Amount to decrement

        Returns:
            New value
        """
        return cache.decr(self.build_key(key), amount)

    def clear_all(self) -> None:
        """
        Clear all cache entries in the current namespace and version.
        """
        self.invalidate_pattern("")

    def bump_version(self) -> None:
        """
        Increment the cache version, effectively invalidating all current keys.
        """
        self.version += 1


# Create a global instance for convenience
default_cache_manager = CacheManager()
