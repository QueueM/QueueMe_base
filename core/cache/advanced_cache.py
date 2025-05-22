"""
Advanced Caching System

This module provides a sophisticated caching system with the following features:
- Multi-level caching (memory + Redis)
- Cache hierarchies with automatic invalidation
- Cache versioning
- Adaptive TTL
- Circuit breaker pattern for cache failures
- Cache result analytics
"""

import base64
import functools
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Default cache settings
DEFAULT_CACHE_TTL = getattr(settings, "DEFAULT_CACHE_TTL", 60 * 5)  # 5 minutes
LONG_CACHE_TTL = getattr(settings, "LONG_CACHE_TTL", 60 * 60 * 24)  # 24 hours
SHORT_CACHE_TTL = getattr(settings, "SHORT_CACHE_TTL", 60)  # 1 minute

# Cache key prefixes by domain
CACHE_PREFIXES = {
    "service": "svc:",
    "booking": "bkg:",
    "specialist": "spc:",
    "shop": "shp:",
    "user": "usr:",
    "customer": "cust:",
    "availability": "avl:",
    "recommendation": "rec:",
    "analytics": "anl:",
}

# In-memory cache for extremely frequent access patterns
# Limited size to avoid memory issues
LOCAL_CACHE_MAX_ITEMS = 1000
local_cache = {}
local_cache_hits = 0
local_cache_misses = 0


def secure_hash(
    data: Union[str, bytes], length: int = 8, used_for_security: bool = False
) -> str:
    """
    Create a secure hash of data using SHA-256

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


class CacheHierarchy:
    """
    Represents a hierarchical relationship between cache keys
    where invalidation of a parent cascades to children
    """

    def __init__(self):
        self.parent_to_children = {}
        self.child_to_parents = {}

    def add_relationship(self, parent_key: str, child_key: str) -> None:
        """Add a parent-child relationship"""
        if parent_key == child_key:
            return  # Avoid circular references

        # Add to parent -> children mapping
        if parent_key not in self.parent_to_children:
            self.parent_to_children[parent_key] = set()
        self.parent_to_children[parent_key].add(child_key)

        # Add to child -> parents mapping
        if child_key not in self.child_to_parents:
            self.child_to_parents[child_key] = set()
        self.child_to_parents[child_key].add(parent_key)

    def get_children(self, parent_key: str, recursive: bool = False) -> Set[str]:
        """Get all children for a parent key"""
        if parent_key not in self.parent_to_children:
            return set()

        children = self.parent_to_children[parent_key].copy()

        if recursive:
            # Recursively get children of children
            for child in list(
                children
            ):  # Create a copy to avoid modification during iteration
                children.update(self.get_children(child, recursive=True))

        return children

    def get_parents(self, child_key: str, recursive: bool = False) -> Set[str]:
        """Get all parents for a child key"""
        if child_key not in self.child_to_parents:
            return set()

        parents = self.child_to_parents[child_key].copy()

        if recursive:
            # Recursively get parents of parents
            for parent in list(
                parents
            ):  # Create a copy to avoid modification during iteration
                parents.update(self.get_parents(parent, recursive=True))

        return parents


# Initialize the cache hierarchy
cache_hierarchy = CacheHierarchy()


class AdvancedCache:
    """
    Advanced caching system with multi-level storage, versioning and more
    """

    def __init__(self, namespace: str = None):
        """Initialize with an optional namespace"""
        self.namespace = namespace
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_check_time = None
        self.version = 1  # Cache version

    def _get_key(self, key: str) -> str:
        """Generate a namespaced key"""
        if self.namespace:
            prefix = CACHE_PREFIXES.get(self.namespace, f"{self.namespace}:")
            return f"{prefix}{key}:v{self.version}"
        return f"cache:{key}:v{self.version}"

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        try:
            # Use JSON for serialization instead of pickle for security
            # For complex objects, use base64 encoding
            serialized = json.dumps(
                value,
                default=lambda o: {
                    "__type__": o.__class__.__name__,
                    "__repr__": repr(o),
                    "data": (
                        base64.b64encode(str(o).encode()).decode()
                        if hasattr(o, "__str__")
                        else None
                    ),
                },
            )
            return serialized.encode("utf-8")
        except TypeError:
            # Fallback for objects that can't be JSON serialized
            return json.dumps(str(value)).encode("utf-8")

    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage with safe handling of untrusted data"""
        if not value:
            return None

        try:
            # First try to deserialize as JSON (preferred method)
            return json.loads(value.decode("utf-8"))
        except json.JSONDecodeError:
            # Fallback: try to interpret as plain string
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                # Last resort: return raw bytes
                return value

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows operation"""
        if not self.circuit_open:
            return True

        # If circuit is open, check if it's time to try again
        if self.circuit_check_time and datetime.now() > self.circuit_check_time:
            self.circuit_open = False
            self.failure_count = 0
            return True

        return False

    def _handle_failure(self) -> None:
        """Handle a cache operation failure"""
        self.failure_count += 1

        # If too many failures, open the circuit
        if self.failure_count >= 3:
            self.circuit_open = True
            self.circuit_check_time = datetime.now() + timedelta(minutes=1)
            logger.warning(
                f"Cache circuit breaker tripped for namespace {self.namespace}"
            )

    def _add_to_local_cache(self, key: str, value: Any, ttl: int) -> None:
        """Add item to local in-memory cache"""
        if len(local_cache) >= LOCAL_CACHE_MAX_ITEMS:
            # Eviction policy: remove oldest item
            oldest_key = min(local_cache.items(), key=lambda x: x[1]["timestamp"])[0]
            del local_cache[oldest_key]

        full_key = self._get_key(key)
        local_cache[full_key] = {
            "value": value,
            "expires": int(time.time()) + ttl,
            "timestamp": int(time.time()),
        }

    def _get_from_local_cache(self, key: str) -> Tuple[bool, Any]:
        """Try to get item from local cache"""
        global local_cache_hits, local_cache_misses

        full_key = self._get_key(key)
        if full_key in local_cache:
            cache_item = local_cache[full_key]

            # Check if expired
            if cache_item["expires"] < int(time.time()):
                del local_cache[full_key]
                local_cache_misses += 1
                return False, None

            local_cache_hits += 1
            return True, cache_item["value"]

        local_cache_misses += 1
        return False, None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_CACHE_TTL,
        use_local_cache: bool = True,
    ) -> bool:
        """
        Set a value in the cache

        Args:
            key: Cache key
            value: Value to store
            ttl: Time to live in seconds
            use_local_cache: Whether to also store in local memory cache

        Returns:
            True if successful, False otherwise
        """
        if not self._check_circuit_breaker():
            return False

        try:
            full_key = self._get_key(key)

            # Set in Redis cache
            result = cache.set(full_key, self._serialize(value), ttl)

            # Also set in local cache if requested
            if use_local_cache:
                self._add_to_local_cache(key, value, ttl)

            return result
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            self._handle_failure()
            return False

    def get(self, key: str, default: Any = None, use_local_cache: bool = True) -> Any:
        """
        Get a value from the cache

        Args:
            key: Cache key
            default: Default value if key not found
            use_local_cache: Whether to check local memory cache first

        Returns:
            Cached value or default
        """
        if not self._check_circuit_breaker():
            return default

        try:
            # Try local cache first if enabled
            if use_local_cache:
                found, value = self._get_from_local_cache(key)
                if found:
                    return value

            # Fall back to Redis cache
            full_key = self._get_key(key)
            value = cache.get(full_key)

            if value is None:
                return default

            deserialized = self._deserialize(value)

            # Update local cache
            if use_local_cache:
                ttl = cache.ttl(full_key)
                if ttl > 0:  # Only cache if there is a positive TTL
                    self._add_to_local_cache(key, deserialized, ttl)

            return deserialized
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self._handle_failure()
            return default

    def delete(self, key: str, cascade: bool = True) -> bool:
        """
        Delete a key from cache

        Args:
            key: Cache key
            cascade: Whether to also delete child keys in the hierarchy

        Returns:
            True if successful, False otherwise
        """
        if not self._check_circuit_breaker():
            return False

        try:
            full_key = self._get_key(key)

            # Delete from Redis cache
            result = cache.delete(full_key)

            # Delete from local cache
            if full_key in local_cache:
                del local_cache[full_key]

            # Handle cascade deletion of child keys
            if cascade:
                children = cache_hierarchy.get_children(full_key)
                for child_key in children:
                    cache.delete(child_key)
                    if child_key in local_cache:
                        del local_cache[child_key]

            return result
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            self._handle_failure()
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a numeric value in the cache

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value or None if failed
        """
        if not self._check_circuit_breaker():
            return None

        try:
            full_key = self._get_key(key)

            # Increment in Redis cache
            new_value = cache.incr(full_key, amount)

            # Update local cache
            if full_key in local_cache:
                local_cache[full_key]["value"] = new_value

            return new_value
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {e}")
            self._handle_failure()
            return None

    def add_to_hierarchy(self, parent_key: str, child_key: str) -> None:
        """
        Add a parent-child relationship to the cache hierarchy

        Args:
            parent_key: Parent cache key
            child_key: Child cache key
        """
        parent_full = self._get_key(parent_key)
        child_full = self._get_key(child_key)
        cache_hierarchy.add_relationship(parent_full, child_full)

    def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Delete all keys with a given prefix

        Args:
            prefix: Prefix to match

        Returns:
            Number of keys deleted
        """
        if not self._check_circuit_breaker():
            return 0

        try:
            # Get all keys with the prefix
            pattern = f"{self._get_key(prefix)}*"
            keys = []

            # This is an implementation detail that works with django-redis
            client = cache.client.get_client()
            for key in client.scan_iter(pattern):
                keys.append(key)

            # Delete all matching keys
            if keys:
                client.delete(*keys)

                # Also remove from local cache
                for key in keys:
                    if key in local_cache:
                        del local_cache[key]

            return len(keys)
        except Exception as e:
            logger.error(f"Error invalidating by prefix {prefix}: {e}")
            self._handle_failure()
            return 0

    def get_or_set(
        self,
        key: str,
        default_func: Callable[[], Any],
        ttl: int = DEFAULT_CACHE_TTL,
        use_local_cache: bool = True,
    ) -> Any:
        """
        Get a value from cache or set it if missing

        Args:
            key: Cache key
            default_func: Function to call to get default value
            ttl: Time to live in seconds
            use_local_cache: Whether to use local memory cache

        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = self.get(key, None, use_local_cache)
        if value is not None:
            return value

        # Value not in cache, compute it
        value = default_func()

        # Store in cache
        if value is not None:  # Don't cache None values
            self.set(key, value, ttl, use_local_cache)

        return value

    def stats(self) -> Dict[str, Any]:
        """Get statistics about the cache"""
        stats = {
            "namespace": self.namespace,
            "version": self.version,
            "circuit_breaker_status": "open" if self.circuit_open else "closed",
            "failure_count": self.failure_count,
            "circuit_retry_time": self.circuit_check_time,
            "local_cache_size": len(local_cache),
            "local_cache_hits": local_cache_hits,
            "local_cache_misses": local_cache_misses,
        }

        return stats


# Function decorators for easy caching


def cached(
    namespace: str = None,
    key_prefix: str = "",
    ttl: int = DEFAULT_CACHE_TTL,
    arg_keys: List[int] = None,
    kwarg_keys: List[str] = None,
    use_local_cache: bool = True,
):
    """
    Decorator for caching function results

    Args:
        namespace: Cache namespace
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds
        arg_keys: Indices of positional args to include in key
        kwarg_keys: Names of keyword args to include in key
        use_local_cache: Whether to use local memory cache

    Returns:
        Decorated function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Initialize cache with namespace
            cache_obj = AdvancedCache(namespace)

            # Generate cache key based on function name, args and kwargs
            key_parts = [key_prefix or func.__name__]

            # Add selected positional args to key
            if arg_keys:
                for idx in arg_keys:
                    if idx < len(args):
                        key_parts.append(str(args[idx]))
            else:
                # Use all positional args except self/cls
                for idx, arg in enumerate(args):
                    if (
                        idx == 0
                        and func.__name__ in ("__init__", "__new__")
                        or "self" in func.__code__.co_varnames
                    ):
                        continue  # Skip self/cls
                    key_parts.append(str(arg))

            # Add selected keyword args to key
            if kwarg_keys:
                for key in kwarg_keys:
                    if key in kwargs:
                        key_parts.append(f"{key}={kwargs[key]}")
            else:
                # Use all keyword args
                for key, value in sorted(kwargs.items()):
                    key_parts.append(f"{key}={value}")

            # Create final cache key
            cache_key = "_".join(key_parts)

            # Try to get from cache or compute
            return cache_obj.get_or_set(
                cache_key, lambda: func(*args, **kwargs), ttl, use_local_cache
            )

        return wrapper

    return decorator


def model_cache_key(model_instance: Model, prefix: str = "") -> str:
    """
    Generate a cache key for a model instance

    Args:
        model_instance: Django model instance
        prefix: Optional prefix

    Returns:
        Cache key string
    """
    model_name = model_instance.__class__.__name__.lower()
    if hasattr(model_instance, "pk") and model_instance.pk:
        return f"{prefix}{model_name}_{model_instance.pk}"

    # For unsaved instances, use object hash
    obj_hash = secure_hash(str(model_instance.__dict__).encode("utf-8"))
    return f"{prefix}{model_name}_unsaved_{obj_hash}"


def invalidate_model_cache(
    model_class: type, instance_id: Any = None, namespace: str = None
) -> None:
    """
    Invalidate cache entries for a model (or specific instance)

    Args:
        model_class: Django model class
        instance_id: Optional specific instance ID to invalidate
        namespace: Cache namespace
    """
    cache_obj = AdvancedCache(namespace)
    model_name = model_class.__name__.lower()

    if instance_id:
        # Invalidate specific instance
        key = f"{model_name}_{instance_id}"
        cache_obj.delete(key, cascade=True)
    else:
        # Invalidate all instances
        cache_obj.invalidate_by_prefix(f"{model_name}_")


# Signal handlers for automatic cache invalidation


@receiver(post_save)
def invalidate_on_save(sender, instance, **kwargs):
    """Invalidate cache when a model instance is saved"""
    # Exclude Django's built-in models
    if sender.__module__.startswith("django."):
        return

    try:
        model_name = sender.__name__.lower()
        cache_obj = AdvancedCache(model_name)

        # Delete the specific instance cache and any related keys
        key = model_cache_key(instance)
        cache_obj.delete(key, cascade=True)

        # Also invalidate list caches
        cache_obj.invalidate_by_prefix(f"{model_name}_list")
    except Exception as e:
        logger.error(f"Error invalidating cache on save: {e}")


@receiver(post_delete)
def invalidate_on_delete(sender, instance, **kwargs):
    """Invalidate cache when a model instance is deleted"""
    # Exclude Django's built-in models
    if sender.__module__.startswith("django."):
        return

    try:
        model_name = sender.__name__.lower()
        cache_obj = AdvancedCache(model_name)

        # Delete the specific instance cache and any related keys
        key = model_cache_key(instance)
        cache_obj.delete(key, cascade=True)

        # Also invalidate list caches
        cache_obj.invalidate_by_prefix(f"{model_name}_list")
    except Exception as e:
        logger.error(f"Error invalidating cache on delete: {e}")


# Create cache instances for common models
service_cache = AdvancedCache("service")
booking_cache = AdvancedCache("booking")
specialist_cache = AdvancedCache("specialist")
shop_cache = AdvancedCache("shop")
user_cache = AdvancedCache("user")
customer_cache = AdvancedCache("customer")
availability_cache = AdvancedCache("availability")
recommendation_cache = AdvancedCache("recommendation")
analytics_cache = AdvancedCache("analytics")
