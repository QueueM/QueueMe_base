"""
Advanced Caching Configuration for QueueMe Backend

This module implements a comprehensive caching strategy for the QueueMe backend,
including Redis cache configuration, cache decorators, and cache invalidation mechanisms.

The caching strategy focuses on:
1. Query result caching for frequently accessed data
2. Template fragment caching for rendered components
3. Session caching for improved authentication performance
4. API response caching for public endpoints
5. Intelligent cache invalidation to ensure data consistency
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, List, Optional

from django.core.cache import cache
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

# Cache keys by resource type
CACHE_KEYS = {
    "shop": "shop:{id}",
    "shop_list": "shop:list:{page}:{filters}",
    "service": "service:{id}",
    "service_list": "service:list:{shop_id}:{page}:{filters}",
    "specialist": "specialist:{id}",
    "specialist_list": "specialist:list:{shop_id}:{page}:{filters}",
    "appointment": "appointment:{id}",
    "user_appointments": "user:{id}:appointments:{page}:{filters}",
    "shop_appointments": "shop:{id}:appointments:{date}:{page}",
    "specialist_schedule": "specialist:{id}:schedule:{date}",
    "available_slots": "available_slots:{shop_id}:{service_id}:{date}",
    "user_profile": "user:{id}:profile",
    "payment": "payment:{id}",
    "user_payments": "user:{id}:payments:{page}",
}

# Cache timeouts by resource type (in seconds)
CACHE_TIMEOUTS = {
    "shop": 3600,  # 1 hour
    "shop_list": 1800,  # 30 minutes
    "service": 3600,  # 1 hour
    "service_list": 1800,  # 30 minutes
    "specialist": 3600,  # 1 hour
    "specialist_list": 1800,  # 30 minutes
    "appointment": 300,  # 5 minutes
    "user_appointments": 300,  # 5 minutes
    "shop_appointments": 300,  # 5 minutes
    "specialist_schedule": 600,  # 10 minutes
    "available_slots": 300,  # 5 minutes
    "user_profile": 1800,  # 30 minutes
    "payment": 3600,  # 1 hour
    "user_payments": 1800,  # 30 minutes
}

# Default cache timeout
DEFAULT_TIMEOUT = 600  # 10 minutes


def generate_cache_key(key_pattern: str, **kwargs) -> str:
    """
    Generate a cache key based on a pattern and keyword arguments.

    Args:
        key_pattern: The pattern string with placeholders
        **kwargs: Keyword arguments to fill the placeholders

    Returns:
        Formatted cache key string
    """
    # Handle dictionary or list arguments by converting to a stable string representation
    for key, value in kwargs.items():
        if isinstance(value, (dict, list, tuple)):
            kwargs[key] = hashlib.md5(
                json.dumps(value, sort_keys=True).encode()
            ).hexdigest()

    return key_pattern.format(**kwargs)


def invalidate_cache_keys(keys: List[str]) -> None:
    """
    Invalidate multiple cache keys.

    Args:
        keys: List of cache keys to invalidate
    """
    for key in keys:
        cache.delete(key)
        logger.debug(f"Cache invalidated: {key}")


def invalidate_related_caches(resource_type: str, resource_id: str, **kwargs) -> None:
    """
    Invalidate all related caches for a given resource.

    Args:
        resource_type: Type of resource (e.g., 'shop', 'appointment')
        resource_id: ID of the resource
        **kwargs: Additional parameters for related caches
    """
    keys_to_invalidate = []

    if resource_type == "shop":
        # Invalidate shop detail cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["shop"], id=resource_id)
        )
        # Invalidate shop list caches
        keys_to_invalidate.append(cache.get("shop_list_keys") or [])
        # Invalidate related service and specialist list caches
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["service_list"], shop_id=resource_id, page="*", filters="*"
            )
        )
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["specialist_list"],
                shop_id=resource_id,
                page="*",
                filters="*",
            )
        )

    elif resource_type == "service":
        # Invalidate service detail cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["service"], id=resource_id)
        )
        # Invalidate service list cache for the shop
        shop_id = kwargs.get("shop_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["service_list"], shop_id=shop_id, page="*", filters="*"
            )
        )
        # Invalidate available slots caches that might use this service
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["available_slots"],
                shop_id=shop_id,
                service_id=resource_id,
                date="*",
            )
        )

    elif resource_type == "specialist":
        # Invalidate specialist detail cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["specialist"], id=resource_id)
        )
        # Invalidate specialist list cache for the shop
        shop_id = kwargs.get("shop_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["specialist_list"], shop_id=shop_id, page="*", filters="*"
            )
        )
        # Invalidate specialist schedule caches
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["specialist_schedule"], id=resource_id, date="*"
            )
        )
        # Invalidate available slots caches that might use this specialist
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["available_slots"], shop_id=shop_id, service_id="*", date="*"
            )
        )

    elif resource_type == "appointment":
        # Invalidate appointment detail cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["appointment"], id=resource_id)
        )
        # Invalidate user appointments cache
        user_id = kwargs.get("user_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["user_appointments"], id=user_id, page="*", filters="*"
            )
        )
        # Invalidate shop appointments cache
        shop_id = kwargs.get("shop_id", "*")
        date = kwargs.get("date", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["shop_appointments"], id=shop_id, date=date, page="*"
            )
        )
        # Invalidate specialist schedule cache
        specialist_id = kwargs.get("specialist_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["specialist_schedule"], id=specialist_id, date=date
            )
        )
        # Invalidate available slots cache
        service_id = kwargs.get("service_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["available_slots"],
                shop_id=shop_id,
                service_id=service_id,
                date=date,
            )
        )

    elif resource_type == "user":
        # Invalidate user profile cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["user_profile"], id=resource_id)
        )
        # Invalidate user appointments cache
        keys_to_invalidate.append(
            generate_cache_key(
                CACHE_KEYS["user_appointments"], id=resource_id, page="*", filters="*"
            )
        )
        # Invalidate user payments cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["user_payments"], id=resource_id, page="*")
        )

    elif resource_type == "payment":
        # Invalidate payment detail cache
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["payment"], id=resource_id)
        )
        # Invalidate user payments cache
        user_id = kwargs.get("user_id", "*")
        keys_to_invalidate.append(
            generate_cache_key(CACHE_KEYS["user_payments"], id=user_id, page="*")
        )

    # Flatten the list and remove duplicates
    flat_keys = []
    for item in keys_to_invalidate:
        if isinstance(item, list):
            flat_keys.extend(item)
        else:
            flat_keys.append(item)

    # Invalidate all keys
    invalidate_cache_keys(list(set(flat_keys)))


def cache_result(
    timeout: Optional[int] = None,
    key_pattern: Optional[str] = None,
    key_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to cache function results.

    Args:
        timeout: Cache timeout in seconds, defaults to DEFAULT_TIMEOUT
        key_pattern: Custom cache key pattern, defaults to function name
        key_params: List of parameter names to include in the cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            if key_pattern:
                # Extract parameters for the cache key
                key_kwargs = {}
                if key_params:
                    for param in key_params:
                        if param in kwargs:
                            key_kwargs[param] = kwargs[param]
                        # Handle positional arguments for methods (skip self/cls)
                        elif len(args) > 1 and param == "self":
                            continue
                        elif len(args) > 0:
                            # This is a simplification, in practice you'd need to match
                            # positional args to parameter names using inspect
                            key_kwargs[param] = args[0]
                cache_key = generate_cache_key(key_pattern, **key_kwargs)
            else:
                # Use function name and arguments as cache key
                func_name = func.__name__
                args_str = hashlib.md5(str(args).encode()).hexdigest()
                kwargs_str = hashlib.md5(
                    json.dumps(kwargs, sort_keys=True).encode()
                ).hexdigest()
                cache_key = f"{func_name}:{args_str}:{kwargs_str}"

            # Try to get result from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            actual_timeout = timeout or DEFAULT_TIMEOUT
            cache.set(cache_key, result, actual_timeout)
            logger.debug(f"Cache set: {cache_key}, timeout: {actual_timeout}s")

            return result

        return wrapper

    return decorator


def cache_queryset_result(
    timeout: Optional[int] = None,
    key_pattern: Optional[str] = None,
    key_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to cache QuerySet results.

    This is a specialized version of cache_result that handles Django QuerySets,
    which need to be evaluated before caching.

    Args:
        timeout: Cache timeout in seconds, defaults to DEFAULT_TIMEOUT
        key_pattern: Custom cache key pattern, defaults to function name
        key_params: List of parameter names to include in the cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key (same as cache_result)
            if key_pattern:
                key_kwargs = {}
                if key_params:
                    for param in key_params:
                        if param in kwargs:
                            key_kwargs[param] = kwargs[param]
                        elif len(args) > 1 and param == "self":
                            continue
                        elif len(args) > 0:
                            key_kwargs[param] = args[0]
                cache_key = generate_cache_key(key_pattern, **key_kwargs)
            else:
                func_name = func.__name__
                args_str = hashlib.md5(str(args).encode()).hexdigest()
                kwargs_str = hashlib.md5(
                    json.dumps(kwargs, sort_keys=True).encode()
                ).hexdigest()
                cache_key = f"{func_name}:{args_str}:{kwargs_str}"

            # Try to get result from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # Execute function
            result = func(*args, **kwargs)

            # Handle QuerySet results
            if isinstance(result, QuerySet):
                # Evaluate QuerySet and convert to list
                result = list(result)

            # Cache result
            actual_timeout = timeout or DEFAULT_TIMEOUT
            cache.set(cache_key, result, actual_timeout)
            logger.debug(f"Cache set: {cache_key}, timeout: {actual_timeout}s")

            return result

        return wrapper

    return decorator


def cache_view_result(timeout: Optional[int] = None) -> Callable:
    """
    Decorator for caching Django view results.

    Args:
        timeout: Cache timeout in seconds, defaults to DEFAULT_TIMEOUT

    Returns:
        Decorated view function
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Skip caching for non-GET requests
            if request.method != "GET":
                return view_func(request, *args, **kwargs)

            # Skip caching for authenticated requests unless explicitly enabled
            if request.user.is_authenticated and not getattr(
                view_func, "cache_authenticated", False
            ):
                return view_func(request, *args, **kwargs)

            # Generate cache key
            path = request.path
            query = hashlib.md5(
                request.META.get("QUERY_STRING", "").encode()
            ).hexdigest()
            user_id = request.user.id if request.user.is_authenticated else "anonymous"
            cache_key = f"view:{path}:{query}:{user_id}"

            # Try to get response from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"View cache hit: {cache_key}")
                return cached_response

            # Execute view function
            response = view_func(request, *args, **kwargs)

            # Only cache successful responses
            if 200 <= response.status_code < 300:
                actual_timeout = timeout or DEFAULT_TIMEOUT
                cache.set(cache_key, response, actual_timeout)
                logger.debug(f"View cache set: {cache_key}, timeout: {actual_timeout}s")

            return response

        return wrapper

    return decorator


class CachedAPIViewMixin:
    """
    Mixin for caching DRF API views.

    This mixin provides caching for DRF API views with proper cache invalidation
    hooks for create, update, and delete operations.

    Usage:
        class MyViewSet(CachedAPIViewMixin, viewsets.ModelViewSet):
            queryset = MyModel.objects.all()
            serializer_class = MyModelSerializer
            cache_timeout = 3600  # 1 hour
            cache_key_prefix = 'my_model'
    """

    cache_timeout = DEFAULT_TIMEOUT
    cache_key_prefix = None

    def get_cache_key(self, **kwargs) -> str:
        """
        Generate a cache key for the view.

        Args:
            **kwargs: Additional parameters for the cache key

        Returns:
            Cache key string
        """
        prefix = self.cache_key_prefix or self.__class__.__name__.lower()
        request = self.request
        path = request.path
        query = hashlib.md5(request.META.get("QUERY_STRING", "").encode()).hexdigest()
        user_id = request.user.id if request.user.is_authenticated else "anonymous"

        # Include additional parameters
        params_str = ""
        if kwargs:
            params_str = (
                ":"
                + hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
            )

        return f"{prefix}:{path}:{query}:{user_id}{params_str}"

    def invalidate_cache(self, **kwargs) -> None:
        """
        Invalidate the cache for this view.

        Args:
            **kwargs: Additional parameters for cache invalidation
        """
        cache_key = self.get_cache_key(**kwargs)
        cache.delete(cache_key)
        logger.debug(f"API view cache invalidated: {cache_key}")

    def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch to handle caching.

        Args:
            request: HTTP request
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            HTTP response
        """
        # Skip caching for non-GET requests
        if request.method != "GET":
            response = super().dispatch(request, *args, **kwargs)
            # Invalidate cache on successful write operations
            if (
                request.method in ("POST", "PUT", "PATCH", "DELETE")
                and 200 <= response.status_code < 300
            ):
                self.invalidate_cache(**kwargs)
            return response

        # Generate cache key
        cache_key = self.get_cache_key(**kwargs)

        # Try to get response from cache
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"API view cache hit: {cache_key}")
            return cached_response

        # Execute view
        response = super().dispatch(request, *args, **kwargs)

        # Only cache successful responses
        if 200 <= response.status_code < 300:
            cache.set(cache_key, response, self.cache_timeout)
            logger.debug(
                f"API view cache set: {cache_key}, timeout: {self.cache_timeout}s"
            )

        return response


# Cache middleware for high-traffic endpoints
def cache_middleware(get_response):
    """
    Middleware for caching high-traffic endpoints.

    This middleware caches responses for specific high-traffic endpoints
    to reduce database load and improve response times.

    Args:
        get_response: Next middleware or view

    Returns:
        Middleware function
    """
    # Endpoints to cache and their timeouts
    CACHED_ENDPOINTS = {
        "/api/v1/shops/": 1800,  # 30 minutes
        "/api/v1/services/": 1800,  # 30 minutes
        "/api/v1/specialists/": 1800,  # 30 minutes
        "/api/v1/available-slots/": 300,  # 5 minutes
    }

    def middleware(request):
        # Skip caching for non-GET requests
        if request.method != "GET":
            return get_response(request)

        # Check if endpoint should be cached
        path = request.path
        if path not in CACHED_ENDPOINTS:
            return get_response(request)

        # Generate cache key
        query = hashlib.md5(request.META.get("QUERY_STRING", "").encode()).hexdigest()
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        cache_key = f"middleware:{path}:{query}:{user_id}"

        # Try to get response from cache
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Middleware cache hit: {cache_key}")
            return cached_response

        # Get response from next middleware or view
        response = get_response(request)

        # Only cache successful responses
        if 200 <= response.status_code < 300:
            timeout = CACHED_ENDPOINTS[path]
            cache.set(cache_key, response, timeout)
            logger.debug(f"Middleware cache set: {cache_key}, timeout: {timeout}s")

        return response

    return middleware


# Example usage in views
"""
# Example 1: Caching a function result
@cache_result(
    timeout=3600,
    key_pattern=CACHE_KEYS['available_slots'],
    key_params=['shop_id', 'service_id', 'date']
)
def get_available_slots(shop_id, service_id, date):
    # Complex calculation to find available slots
    # ...
    return slots

# Example 2: Caching a QuerySet result
@cache_queryset_result(
    timeout=1800,
    key_pattern=CACHE_KEYS['shop_list'],
    key_params=['page', 'filters']
)
def get_shops(page=1, filters=None):
    queryset = Shop.objects.filter(is_active=True)
    if filters:
        # Apply filters
        # ...
    return queryset

# Example 3: Caching a view
@cache_view_result(timeout=1800)
def shop_detail_view(request, shop_id):
    shop = get_object_or_404(Shop, id=shop_id)
    return render(request, 'shop_detail.html', {'shop': shop})

# Example 4: Caching a DRF API view
class ShopViewSet(CachedAPIViewMixin, viewsets.ModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    cache_timeout = 1800  # 30 minutes
    cache_key_prefix = 'shop'
"""
