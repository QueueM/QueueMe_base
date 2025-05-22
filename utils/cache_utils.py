"""
Cache utility functions to extend Django's cache capabilities.
"""

import logging
import re
from typing import Optional, Union

from django.core.cache import cache
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def delete_pattern(pattern: str) -> int:
    """
    Delete all cache keys matching a pattern.

    This function works with Redis backends by using Redis's SCAN and DEL commands.
    If a different cache backend is used, it will log a warning.

    Args:
        pattern: Pattern to match cache keys (e.g., "user:*:profile")

    Returns:
        Number of deleted keys
    """
    try:
        # Try to get Redis client from Django's cache
        if hasattr(cache, "client") and hasattr(cache.client, "get_client"):
            # Get Redis client from django-redis
            redis_client = cache.client.get_client()

            if isinstance(redis_client, Redis):
                return _redis_delete_pattern(redis_client, pattern)
    except (AttributeError, ImportError) as e:
        logger.warning(f"Could not access Redis client: {str(e)}")

    # Fallback for other cache backends (less efficient)
    return _fallback_delete_pattern(pattern)


def _redis_delete_pattern(redis_client: Redis, pattern: str) -> int:
    """
    Delete keys matching pattern directly using Redis.

    Args:
        redis_client: Redis client instance
        pattern: Pattern to match keys

    Returns:
        Number of deleted keys
    """
    try:
        # Add cache key prefix if exists
        if hasattr(cache, "key_prefix") and cache.key_prefix:
            pattern = f"{cache.key_prefix}:{pattern}"

        # Use SCAN to find keys matching pattern
        count = 0
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                redis_client.delete(*keys)
                count += len(keys)
            if cursor == 0:
                break

        return count
    except RedisError as e:
        logger.error(f"Redis error when deleting by pattern {pattern}: {str(e)}")
        return 0


def _fallback_delete_pattern(pattern: str) -> int:
    """
    Fallback method for non-Redis cache backends.

    Note: This is much less efficient as it requires getting all keys.

    Args:
        pattern: Pattern to match keys (will be converted to regex)

    Returns:
        Number of deleted keys
    """
    # Convert Redis-style pattern to regex
    regex_pattern = pattern.replace("*", ".*").replace("?", ".")
    regex = re.compile(f"^{regex_pattern}$")

    count = 0

    # This only works if the cache backend implements get_cache_keys()
    if hasattr(cache, "get_cache_keys"):
        all_keys = cache.get_cache_keys()
        matching_keys = [key for key in all_keys if regex.match(key)]

        for key in matching_keys:
            cache.delete(key)
            count += 1
    else:
        logger.warning(
            "Cache backend does not support pattern deletion and doesn't provide get_cache_keys(). "
            "Pattern deletion not supported."
        )

    return count


def clear_cache_for_model(
    model_name: str, object_id: Optional[Union[str, int]] = None
) -> int:
    """
    Clear cache for specific model or object.

    Args:
        model_name: Model name in lowercase (e.g., "user", "appointment")
        object_id: Optional object ID to clear specific object cache

    Returns:
        Number of cache entries deleted
    """
    pattern = f"{model_name}:*" if object_id is None else f"{model_name}:{object_id}:*"
    return delete_pattern(pattern)
