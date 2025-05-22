"""
Tiered Cache Manager

An optimized multi-level caching system that distributes content across
different cache backends based on data characteristics.
"""

import logging
import pickle
import time
from functools import wraps
from typing import Any, Dict, List, Optional, Set

from django.core.cache import caches

logger = logging.getLogger(__name__)

# Default cache TTL values
DEFAULT_CACHE_TTL = 300  # 5 minutes
SHORT_CACHE_TTL = 60  # 1 minute
MEDIUM_CACHE_TTL = 60 * 15  # 15 minutes
LONG_CACHE_TTL = 60 * 60  # 1 hour
VERY_LONG_CACHE_TTL = 60 * 60 * 24  # 1 day

# Cache key prefixes to help with clearing related keys
SHOP_PREFIX = "shop:"
USER_PREFIX = "user:"
QUEUE_PREFIX = "queue:"
SERVICE_PREFIX = "service:"
SPECIALIST_PREFIX = "specialist:"
AVAILABILITY_PREFIX = "availability:"


class TieredCache:
    """
    Tiered cache manager that distributes data across multiple cache backends
    based on data characteristics for optimal performance.

    The tiers are:
    - local_memory: Super fast local process memory (small items, highest hit rate)
    - default: Main Redis cache for most data
    - persistent: Longer-lived data that rarely changes
    - large_objects: Special cache for large serialized objects
    """

    def __init__(self):
        """Initialize cache backends and settings."""
        # Set up available cache backends
        self.local_memory = {}
        self.default = caches["default"]

        # Get additional cache backends if configured
        try:
            self.persistent = caches["persistent"]
        except Exception:
            self.persistent = self.default

        try:
            self.large_objects = caches["large_objects"]
        except Exception:
            self.large_objects = self.default

        # Set up cache key tracking for patterns
        self._key_patterns: Dict[str, Set[str]] = {}

        logger.info("Tiered cache system initialized")

    def get(self, key: str, default=None) -> Any:
        """
        Get a value from the tiered cache system.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            The cached value or default
        """
        # Try local memory first (fastest)
        if key in self.local_memory:
            value, expiry = self.local_memory[key]
            if expiry > time.time():
                return value
            else:
                # Expired, remove from local
                del self.local_memory[key]

        # Try the default cache
        value = self.default.get(key)
        if value is not None:
            # Store in local memory for faster future access
            # Use a short TTL for local memory to prevent stale data
            self._store_local(key, value, SHORT_CACHE_TTL)
            return value

        # Try persistent cache for long-lived data
        if key.startswith((SERVICE_PREFIX, "geo:", "static:")):
            value = self.persistent.get(key)
            if value is not None:
                # Store in default cache for faster future access
                self.default.set(key, value, timeout=MEDIUM_CACHE_TTL)
                self._store_local(key, value, SHORT_CACHE_TTL)
                return value

        # Try large object cache for complex serialized data
        if key.startswith(("report:", "complex:", "full_data:")):
            value = self.large_objects.get(key)
            if value is not None:
                # Don't cache large objects in memory, but do in default cache
                self.default.set(key, value, timeout=SHORT_CACHE_TTL)
                return value

        return default

    def set(
        self,
        key: str,
        value: Any,
        timeout: int = DEFAULT_CACHE_TTL,
        pattern: Optional[str] = None,
    ) -> bool:
        """
        Set a value in the tiered cache system.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            pattern: Optional pattern for grouped invalidation

        Returns:
            Boolean indicating success
        """
        # Track the key in its pattern group if specified
        if pattern:
            if pattern not in self._key_patterns:
                self._key_patterns[pattern] = set()
            self._key_patterns[pattern].add(key)

        # Choose appropriate backend based on key pattern and value size
        try:
            # Store in default cache for most keys
            self.default.set(key, value, timeout=timeout)

            # For long-lived static data, also store in persistent cache
            if (
                key.startswith((SERVICE_PREFIX, "geo:", "static:"))
                and timeout > MEDIUM_CACHE_TTL
            ):
                self.persistent.set(key, value, timeout=timeout)

            # For very large objects, store in large object cache
            if key.startswith(
                ("report:", "complex:", "full_data:")
            ) or _is_large_object(value):
                self.large_objects.set(key, value, timeout=timeout)

            # Store in local memory for fastest access, with shorter timeout
            local_timeout = min(timeout, SHORT_CACHE_TTL)
            self._store_local(key, value, local_timeout)

            return True
        except Exception as e:
            logger.warning(f"Error setting cache key {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a value from all cache tiers.

        Args:
            key: Cache key to delete

        Returns:
            Boolean indicating success
        """
        try:
            # Remove from local memory
            if key in self.local_memory:
                del self.local_memory[key]

            # Remove from other caches
            self.default.delete(key)
            self.persistent.delete(key)
            self.large_objects.delete(key)

            # Remove from pattern tracking
            for pattern, keys in self._key_patterns.items():
                if key in keys:
                    keys.remove(key)

            return True
        except Exception as e:
            logger.warning(f"Error deleting cache key {key}: {str(e)}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a specific pattern.

        Args:
            pattern: Pattern to match (exact match with pattern registered during set)

        Returns:
            Number of keys deleted
        """
        if pattern not in self._key_patterns:
            return 0

        keys = list(self._key_patterns[pattern])
        deleted = 0

        for key in keys:
            if self.delete(key):
                deleted += 1

        # Clear the pattern tracking
        self._key_patterns[pattern] = set()

        return deleted

    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys from all cache tiers.

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys deleted
        """
        deleted = 0
        for key in keys:
            if self.delete(key):
                deleted += 1
        return deleted

    def clear(self) -> bool:
        """
        Clear all caches.

        Returns:
            Boolean indicating success
        """
        try:
            # Clear local memory
            self.local_memory.clear()

            # Clear other caches
            self.default.clear()
            self.persistent.clear()
            self.large_objects.clear()

            # Clear pattern tracking
            self._key_patterns.clear()

            return True
        except Exception as e:
            logger.error(f"Error clearing caches: {str(e)}")
            return False

    def _store_local(self, key: str, value: Any, timeout: int) -> None:
        """Store a value in local memory with expiry time."""
        expiry = time.time() + timeout
        self.local_memory[key] = (value, expiry)


def _is_large_object(value: Any) -> bool:
    """Determine if an object is considered large for caching."""
    try:
        # Serialize and check size
        serialized = pickle.dumps(value)
        return len(serialized) > 100 * 1024  # > 100KB
    except Exception:
        # If can't serialize, assume it's complex
        return True


# Create a global instance
tiered_cache = TieredCache()


def cached(
    key_prefix: str,
    timeout: int = DEFAULT_CACHE_TTL,
    args_to_include: Optional[List[int]] = None,
    kwargs_to_include: Optional[List[str]] = None,
    version: Optional[str] = None,
):
    """
    Decorator for caching function results.

    Args:
        key_prefix: Prefix for the cache key
        timeout: Cache timeout in seconds
        args_to_include: List of positional argument indices to include in key
        kwargs_to_include: List of keyword argument names to include in key
        version: Optional version string to invalidate all cache on change

    Returns:
        Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a cache key based on function and arguments
            key_parts = [key_prefix, func.__module__, func.__name__]

            # Add version if specified
            if version:
                key_parts.append(f"v{version}")

            # Add selected arguments to key
            if args_to_include:
                for i in args_to_include:
                    if i < len(args):
                        key_parts.append(str(args[i]))

            if kwargs_to_include:
                for kwarg in kwargs_to_include:
                    if kwarg in kwargs:
                        key_parts.append(f"{kwarg}:{kwargs[kwarg]}")

            # Create the final key
            key = ":".join(str(part) for part in key_parts)

            # Check for cache hit
            cached_value = tiered_cache.get(key)
            if cached_value is not None:
                return cached_value

            # Cache miss, call the function
            result = func(*args, **kwargs)

            # Store in cache
            tiered_cache.set(key, result, timeout=timeout)

            return result

        return wrapper

    return decorator
