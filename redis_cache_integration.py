"""
Redis Cache Integration for QueueMe Backend

This module implements Redis cache integration for the QueueMe backend,
configuring Redis as the primary cache backend and session store for improved
performance and scalability.

The Redis configuration includes:
1. Connection pooling for efficient resource usage
2. Separate databases for different cache types
3. Serialization/deserialization optimizations
4. Failover and high availability settings
"""

import os


# Redis cache configuration
REDIS_CACHE_CONFIG = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme",
        "TIMEOUT": 300,  # 5 minutes default
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_SESSION_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme_session",
        "TIMEOUT": 86400,  # 24 hours
    },
    "throttling": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_THROTTLE_URL", "redis://127.0.0.1:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "queueme_throttle",
        "TIMEOUT": 3600,  # 1 hour
    },
}

# Session configuration
SESSION_CONFIG = {
    "ENGINE": "django.contrib.sessions.backends.cache",
    "CACHE_ALIAS": "sessions",
    "COOKIE_AGE": 86400,  # 24 hours
    "COOKIE_SECURE": True,
    "COOKIE_HTTPONLY": True,
    "COOKIE_SAMESITE": "Lax",
}

# Cache middleware settings
CACHE_MIDDLEWARE_CONFIG = {
    "CACHE_MIDDLEWARE_SECONDS": 300,  # 5 minutes
    "CACHE_MIDDLEWARE_KEY_PREFIX": "queueme_middleware",
    "CACHE_MIDDLEWARE_ALIAS": "default",
}


# Function to apply Redis cache configuration to Django settings
def apply_redis_cache_config(django_settings):
    """
    Apply Redis cache configuration to Django settings.

    Args:
        django_settings: Django settings module
    """
    # Set cache configuration
    django_settings.CACHES = REDIS_CACHE_CONFIG

    # Set session configuration
    django_settings.SESSION_ENGINE = SESSION_CONFIG["ENGINE"]
    django_settings.SESSION_CACHE_ALIAS = SESSION_CONFIG["CACHE_ALIAS"]
    django_settings.SESSION_COOKIE_AGE = SESSION_CONFIG["COOKIE_AGE"]
    django_settings.SESSION_COOKIE_SECURE = SESSION_CONFIG["COOKIE_SECURE"]
    django_settings.SESSION_COOKIE_HTTPONLY = SESSION_CONFIG["COOKIE_HTTPONLY"]
    django_settings.SESSION_COOKIE_SAMESITE = SESSION_CONFIG["COOKIE_SAMESITE"]

    # Set cache middleware settings
    django_settings.CACHE_MIDDLEWARE_SECONDS = CACHE_MIDDLEWARE_CONFIG[
        "CACHE_MIDDLEWARE_SECONDS"
    ]
    django_settings.CACHE_MIDDLEWARE_KEY_PREFIX = CACHE_MIDDLEWARE_CONFIG[
        "CACHE_MIDDLEWARE_KEY_PREFIX"
    ]
    django_settings.CACHE_MIDDLEWARE_ALIAS = CACHE_MIDDLEWARE_CONFIG[
        "CACHE_MIDDLEWARE_ALIAS"
    ]

    # Add cache middleware to middleware classes if not already present
    cache_middleware = "django.middleware.cache.UpdateCacheMiddleware"
    fetch_middleware = "django.middleware.cache.FetchFromCacheMiddleware"

    if cache_middleware not in django_settings.MIDDLEWARE:
        # Insert UpdateCacheMiddleware at the beginning
        django_settings.MIDDLEWARE.insert(0, cache_middleware)

    if fetch_middleware not in django_settings.MIDDLEWARE:
        # Insert FetchFromCacheMiddleware at the end
        django_settings.MIDDLEWARE.append(fetch_middleware)

    return django_settings
