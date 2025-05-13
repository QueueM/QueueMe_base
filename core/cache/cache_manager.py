"""
Cache Manager

A comprehensive caching system for QueueMe that implements multi-level caching
strategies with intelligent invalidation patterns for optimal performance.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.cache import cache, caches
from django.db.models import Model, QuerySet

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_CACHE = "default"  # Redis-based cache for most operations
LOCAL_CACHE = "local"  # Process/memory cache for very frequent access
LONG_TERM_CACHE = "redis"  # For data that changes infrequently

# Default TTLs by content type
DEFAULT_TTL = 60 * 5  # 5 minutes
TTL_MAPPING = {
    # Category data rarely changes
    "category": 60 * 60 * 24,  # 24 hours
    # Shop information
    "shop": 60 * 60 * 3,  # 3 hours
    "shop_detail": 60 * 30,  # 30 minutes
    # Service information
    "service": 60 * 60,  # 1 hour
    "service_detail": 60 * 15,  # 15 minutes
    # User-related data
    "user_profile": 60 * 60 * 24,  # 24 hours
    "user_preferences": 60 * 60 * 24,  # 24 hours
    # Dynamic data
    "availability": 60 * 5,  # 5 minutes
    "queue_status": 60,  # 1 minute
    "booking_status": 60 * 3,  # 3 minutes
    # Frequently changing data
    "recommendation": 60 * 30,  # 30 minutes
    "trending": 60 * 10,  # 10 minutes
    # Search results
    "search_results": 60 * 3,  # 3 minutes
    # Content-related
    "reel": 60 * 60 * 2,  # 2 hours
    "story": 60 * 15,  # 15 minutes
    # API responses
    "api_response": 60 * 5,  # 5 minutes
    # Computed data
    "analytics": 60 * 60,  # 1 hour
}


def secure_hash(data: Union[str, bytes], length: int = 8, used_for_security: bool = False) -> str:
    """
    Create a secure hash of data

    Args:
        data: String or bytes to hash
        length: Length of the resulting hash digest to return (truncated)
        used_for_security: Whether this hash is used for security purposes

    Returns:
        Truncated hexadecimal digest
    """
    if isinstance(data, str):
        data = data.encode()

    # Use SHA-256 for better security
    hash_func = hashlib.sha256(data, usedforsecurity=used_for_security)
    return hash_func.hexdigest()[:length]


class CacheManager:
    """
    Manages caching operations with intelligent strategies for different data types
    """

    @staticmethod
    def build_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate a consistent cache key with a prefix

        Args:
            prefix: A string prefix for the cache key
            *args: Positional arguments to include in the key
            **kwargs: Keyword arguments to include in the key

        Returns:
            A unique cache key string
        """
        # Build key components
        key_parts = [prefix]

        # Add args
        for arg in args:
            if isinstance(arg, Model):
                # For model instances, use their primary key and class name
                key_parts.append(f"{arg.__class__.__name__}_{arg.pk}")
            elif isinstance(arg, (list, tuple, set)):
                # For collections, use length and hash of contents
                hash_val = secure_hash(str(sorted(arg)).encode())
                key_parts.append(f"col_{len(arg)}_{hash_val}")
            elif isinstance(arg, dict):
                # For dictionaries, use a stable representation
                hash_val = secure_hash(json.dumps(arg, sort_keys=True).encode())
                key_parts.append(f"dict_{hash_val}")
            else:
                # For simple types, use string representation
                key_parts.append(str(arg))

        # Add sorted kwargs
        sorted_kwargs = dict(sorted(kwargs.items()))
        if sorted_kwargs:
            kwargs_str = secure_hash(json.dumps(sorted_kwargs, sort_keys=True).encode())
            key_parts.append(f"kwargs_{kwargs_str}")

        # Join all parts with colons
        key = ":".join([str(k) for k in key_parts])

        # Ensure key is not too long (Redis has a limit)
        if len(key) > 200:
            hash_val = secure_hash(key.encode())
            key = f"{prefix}:hash:{hash_val}"

        return key

    @staticmethod
    def get(key: str, default=None, cache_name=DEFAULT_CACHE) -> Any:
        """
        Retrieve a value from cache

        Args:
            key: Cache key string
            default: Default value if key is not in cache
            cache_name: The cache backend to use

        Returns:
            The cached value or the default
        """
        try:
            cache_backend = caches[cache_name]
            value = cache_backend.get(key, default)

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                result = "HIT" if value is not default else "MISS"
                logger.debug(f"Cache {result}: {key} from {cache_name}")

            return value
        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return default

    @staticmethod
    def set(key: str, value: Any, ttl=None, cache_name=DEFAULT_CACHE) -> bool:
        """
        Store a value in cache

        Args:
            key: Cache key string
            value: Value to cache
            ttl: Time-to-live in seconds or None for default
            cache_name: The cache backend to use

        Returns:
            Boolean indicating success
        """
        try:
            if ttl is None:
                # Determine TTL based on key prefix
                for prefix, ttl_value in TTL_MAPPING.items():
                    if key.startswith(f"{prefix}:"):
                        ttl = ttl_value
                        break
                else:
                    ttl = DEFAULT_TTL

            cache_backend = caches[cache_name]
            cache_backend.set(key, value, ttl)

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                logger.debug(f"Cache SET: {key} in {cache_name} with TTL={ttl}")

            return True
        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            return False

    @staticmethod
    def delete(key: str, cache_name=DEFAULT_CACHE) -> bool:
        """
        Remove a value from cache

        Args:
            key: Cache key string
            cache_name: The cache backend to use

        Returns:
            Boolean indicating success
        """
        try:
            cache_backend = caches[cache_name]
            cache_backend.delete(key)

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                logger.debug(f"Cache DELETE: {key} from {cache_name}")

            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key '{key}': {e}")
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all keys matching a pattern (for Redis backends)

        Args:
            pattern: Pattern to match keys

        Returns:
            Number of keys deleted
        """
        try:
            redis_cache = caches[DEFAULT_CACHE]

            # Access Redis client directly
            if hasattr(redis_cache, "client") and hasattr(redis_cache.client, "delete_pattern"):
                count = redis_cache.client.delete_pattern(pattern)

                # Debugging if enabled
                if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                    logger.debug(f"Cache DELETE_PATTERN: {pattern}, deleted {count} keys")

                return count
            else:
                # Fallback for non-Redis backends or if delete_pattern is not available
                logger.warning("Cache delete_pattern not available for the cache backend")
                return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error for pattern '{pattern}': {e}")
            return 0

    @staticmethod
    def get_multi(keys: List[str], cache_name=DEFAULT_CACHE) -> Dict[str, Any]:
        """
        Retrieve multiple values from cache in one operation

        Args:
            keys: List of cache key strings
            cache_name: The cache backend to use

        Returns:
            Dictionary mapping keys to values
        """
        try:
            cache_backend = caches[cache_name]

            # Check if backend supports get_many
            if hasattr(cache_backend, "get_many"):
                return cache_backend.get_many(keys)
            else:
                # Fallback for backends without get_many
                result = {}
                for key in keys:
                    value = cache_backend.get(key)
                    if value is not None:
                        result[key] = value
                return result
        except Exception as e:
            logger.warning(f"Cache get_multi error: {e}")
            return {}

    @staticmethod
    def set_multi(data: Dict[str, Any], ttl=None, cache_name=DEFAULT_CACHE) -> bool:
        """
        Store multiple values in cache in one operation

        Args:
            data: Dictionary mapping keys to values
            ttl: Time-to-live in seconds or None for default
            cache_name: The cache backend to use

        Returns:
            Boolean indicating success
        """
        try:
            cache_backend = caches[cache_name]

            # Determine TTL for each key if not provided
            if ttl is None:
                for key in data:
                    key_ttl = DEFAULT_TTL
                    for prefix, ttl_value in TTL_MAPPING.items():
                        if key.startswith(f"{prefix}:"):
                            key_ttl = ttl_value
                            break

                    # Check if backend supports set_many
                    if hasattr(cache_backend, "set_many"):
                        cache_backend.set_many(data, key_ttl)
                    else:
                        # Fallback for backends without set_many
                        for k, v in data.items():
                            cache_backend.set(k, v, key_ttl)
            else:
                # Use the provided TTL for all keys
                if hasattr(cache_backend, "set_many"):
                    cache_backend.set_many(data, ttl)
                else:
                    # Fallback for backends without set_many
                    for k, v in data.items():
                        cache_backend.set(k, v, ttl)

            return True
        except Exception as e:
            logger.warning(f"Cache set_multi error: {e}")
            return False

    @staticmethod
    def invalidate_related(model_instance: Model, cache_types: List[str] = None) -> int:
        """
        Invalidate cache entries related to a model instance

        Args:
            model_instance: The model instance that was changed
            cache_types: Optional list of specific cache types to invalidate

        Returns:
            Number of keys invalidated
        """
        try:
            model_name = model_instance.__class__.__name__.lower()
            model_id = str(model_instance.pk)

            # Default to common cache types for model if not specified
            if cache_types is None:
                cache_types = [model_name, f"{model_name}_detail"]

                # Add related types for specific models
                if model_name == "shop":
                    cache_types.extend(["service", "specialist", "availability"])
                elif model_name == "service":
                    cache_types.extend(["availability", "shop"])
                elif model_name == "specialist":
                    cache_types.extend(["availability", "service"])
                elif model_name == "appointment":
                    cache_types.extend(["availability", "booking_status"])
                elif model_name == "queueticket":
                    cache_types.extend(["queue_status"])

            # Create patterns for each type
            patterns = []
            for cache_type in cache_types:
                patterns.append(f"{cache_type}:*{model_name}_{model_id}*")
                patterns.append(f"{cache_type}:*{model_id}*")

            # Delete all matching keys
            count = 0
            for pattern in patterns:
                count += CacheManager.delete_pattern(pattern)

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                logger.debug(f"Cache invalidated {count} keys for {model_name} {model_id}")

            return count
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")
            return 0

    @staticmethod
    def invalidate_model(model_class: type, cache_types: List[str] = None) -> int:
        """
        Invalidate all cache entries for a model type

        Args:
            model_class: The model class to invalidate
            cache_types: Optional list of specific cache types to invalidate

        Returns:
            Number of keys invalidated
        """
        try:
            model_name = model_class.__name__.lower()

            # Default to common cache types for model if not specified
            if cache_types is None:
                cache_types = [model_name, f"{model_name}_detail"]

            # Create patterns for each type
            patterns = []
            for cache_type in cache_types:
                patterns.append(f"{cache_type}:*{model_name}*")

            # Delete all matching keys
            count = 0
            for pattern in patterns:
                count += CacheManager.delete_pattern(pattern)

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                logger.debug(f"Cache invalidated {count} keys for model {model_name}")

            return count
        except Exception as e:
            logger.warning(f"Cache model invalidation error: {e}")
            return 0

    @staticmethod
    def cached(
        prefix: str,
        ttl: int = None,
        cache_name: str = DEFAULT_CACHE,
        model_cls: type = None,
        vary_on: List[str] = None,
    ):
        """
        Decorator for caching function results

        Args:
            prefix: Prefix for the cache key
            ttl: Time-to-live in seconds, or None for default
            cache_name: The cache backend to use
            model_cls: Optional model class for automatic invalidation
            vary_on: List of argument names to include in the cache key

        Returns:
            Decorated function
        """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Build cache key
                key_parts = [prefix, func.__name__]

                # Add function arguments to key if needed
                if vary_on:
                    # Map arg names to positional args
                    arg_dict = {}
                    arg_names = func.__code__.co_varnames[: func.__code__.co_argcount]
                    for i, arg_name in enumerate(arg_names):
                        if i < len(args):
                            arg_dict[arg_name] = args[i]

                    # Add keyword args
                    arg_dict.update(kwargs)

                    # Add specified args to key
                    for arg_name in vary_on:
                        if arg_name in arg_dict:
                            key_parts.append(f"{arg_name}={arg_dict[arg_name]}")

                # Final key
                if len(key_parts) > 2:
                    key = CacheManager.build_key(*key_parts)
                else:
                    # Simple key for functions without variation
                    key = ":".join(key_parts)

                # Try to get from cache
                cached_value = CacheManager.get(key, cache_name=cache_name)
                if cached_value is not None:
                    return cached_value

                # Call function and cache result
                result = func(*args, **kwargs)
                CacheManager.set(key, result, ttl=ttl, cache_name=cache_name)

                return result

            # Attach meta information to function for cache management
            wrapper._cache_info = {
                "prefix": prefix,
                "ttl": ttl,
                "cache_name": cache_name,
                "model_class": model_cls,
            }

            return wrapper

        return decorator

    @staticmethod
    def cached_property(
        prefix: str,
        ttl: int = None,
        cache_name: str = DEFAULT_CACHE,
        include_self: bool = True,
        include_args: bool = False,
    ):
        """
        Decorator for caching properties

        Args:
            prefix: Prefix for the cache key
            ttl: Time-to-live in seconds, or None for default
            cache_name: The cache backend to use
            include_self: Whether to include the instance in the cache key
            include_args: Whether to include method arguments in the cache key

        Returns:
            Decorated property method
        """

        def decorator(method):
            @wraps(method)
            def wrapper(self, *args, **kwargs):
                # Build cache key
                key_parts = [prefix, method.__name__]

                # Add self to key if specified
                if include_self and hasattr(self, "pk"):
                    key_parts.append(f"{self.__class__.__name__}_{self.pk}")

                # Add args to key if specified
                if include_args and (args or kwargs):
                    # Convert args to string representations
                    args_str = ",".join(map(str, args))
                    if args_str:
                        key_parts.append(f"args={args_str}")

                    # Convert kwargs to stable string representation
                    if kwargs:
                        sorted_kwargs = dict(sorted(kwargs.items()))
                        kwargs_str = ",".join(f"{k}={v}" for k, v in sorted_kwargs.items())
                        key_parts.append(f"kwargs={kwargs_str}")

                # Final key
                key = CacheManager.build_key(*key_parts)

                # Try to get from cache
                cached_value = CacheManager.get(key, cache_name=cache_name)
                if cached_value is not None:
                    return cached_value

                # Call method and cache result
                result = method(self, *args, **kwargs)
                CacheManager.set(key, result, ttl=ttl, cache_name=cache_name)

                return result

            return wrapper

        return decorator

    @staticmethod
    def cache_queryset(
        queryset: QuerySet, key: str, ttl: int = None, cache_name: str = DEFAULT_CACHE
    ) -> List[dict]:
        """
        Cache a queryset as serialized data

        Args:
            queryset: The queryset to cache
            key: Cache key
            ttl: Time-to-live in seconds, or None for default
            cache_name: The cache backend to use

        Returns:
            List of dictionaries representing the queryset
        """
        try:
            # Check if queryset is cached
            cached_data = CacheManager.get(key, cache_name=cache_name)
            if cached_data is not None:
                return cached_data

            # Evaluate queryset and convert to dictionaries
            data = list(queryset.values())

            # Cache the result
            CacheManager.set(key, data, ttl=ttl, cache_name=cache_name)

            return data
        except Exception as e:
            logger.warning(f"Cache queryset error: {e}")
            # Fallback to returning the evaluated queryset without caching
            return list(queryset.values())

    @staticmethod
    def invalidate_all():
        """
        Clear the entire cache (use with caution)

        Returns:
            Boolean indicating success
        """
        try:
            # Clear default cache
            cache.clear()

            # Clear other caches
            for cache_name in settings.CACHES.keys():
                if cache_name != DEFAULT_CACHE:
                    caches[cache_name].clear()

            # Debugging if enabled
            if settings.DEBUG and getattr(settings, "CACHE_DEBUG", False):
                logger.debug("All caches have been cleared")

            return True
        except Exception as e:
            logger.warning(f"Cache invalidate_all error: {e}")
            return False

    @staticmethod
    def monitor():
        """
        Get cache statistics and usage information

        Returns:
            Dictionary with cache statistics
        """
        try:
            stats = {}

            # Get stats for each cache
            for cache_name in settings.CACHES.keys():
                cache_backend = caches[cache_name]

                # Try to get stats if available
                if hasattr(cache_backend, "get_stats"):
                    stats[cache_name] = cache_backend.get_stats()
                elif hasattr(cache_backend, "info"):
                    # Redis specific
                    stats[cache_name] = cache_backend.info()
                else:
                    stats[cache_name] = {
                        "status": "Available",
                        "stats_not_supported": True,
                    }

            return stats
        except Exception as e:
            logger.warning(f"Cache monitor error: {e}")
            return {"error": str(e)}


# Convenience aliases
cache_manager = CacheManager()
build_key = CacheManager.build_key
cached = CacheManager.cached
cached_property = CacheManager.cached_property
invalidate_related = CacheManager.invalidate_related
invalidate_model = CacheManager.invalidate_model


def cache_with_key_prefix(prefix, timeout=None):
    """
    Decorator for caching function results with a simpler interface.

    Args:
        prefix: Prefix for the cache key
        timeout: Time-to-live in seconds, or None for default

    Returns:
        Decorated function
    """
    return CacheManager.cached(prefix=prefix, ttl=timeout)
