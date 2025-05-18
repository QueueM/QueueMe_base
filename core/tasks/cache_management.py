"""
Cache management tasks for QueueMe.

This module provides scheduled tasks for maintaining Redis cache health,
including clearing stale cache entries and monitoring cache memory usage.
"""

import logging
from datetime import datetime

from celery import shared_task
from django.core.cache import cache
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)


@shared_task
def clear_stale_caches():
    """
    Clear specific cache patterns that need regular refresh.

    This task deletes caches matching certain patterns to prevent stale data
    from accumulating in the cache store.

    Returns:
        str: Summary of cleared cache entries
    """
    # Define patterns for caches that should be regularly cleared
    patterns = [
        # Appointment-related caches - often become stale after a day
        "specialist_appointments_*",
        "customer_appointments_*",
        "service_appointments_*",
        "shop_appointments_*",
        # Queue-related caches
        "queue_length_*",
        "queue_position_*",
        "queue_wait_time_*",
        # Analytics caches that may hold outdated statistics
        "analytics_daily_*",
        "analytics_monthly_*",
        "dashboard_stats_*",
        # Other potentially stale caches
        "availability_*_[0-9]*",
        "search_results_*",
    ]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cleared_count = 0

    for pattern in patterns:
        try:
            # Note: delete_pattern requires django-redis
            result = cache.delete_pattern(pattern)
            cleared_count += result if result else 0

            if result:
                logger.info(f"[{timestamp}] Cleared {result} caches matching pattern '{pattern}'")

        except Exception as e:
            logger.error(
                f"[{timestamp}] Error clearing cache pattern '{pattern}': {str(e)}", exc_info=True
            )

    return f"Cleared {cleared_count} cache entries at {timestamp}"


@shared_task
def monitor_cache_size():
    """
    Monitor Redis cache size and log warnings if it exceeds thresholds.

    This task checks the current memory usage of Redis and logs warnings
    if it exceeds defined thresholds.

    Returns:
        dict: Memory usage statistics
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Get Redis connection and stats
        client = get_redis_connection("default")
        info = client.info(section="memory")

        # Calculate memory usage in MB
        used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
        used_memory_peak_mb = info.get("used_memory_peak", 0) / (1024 * 1024)
        used_memory_rss_mb = info.get("used_memory_rss", 0) / (1024 * 1024)

        # Log memory usage
        logger.info(
            f"[{timestamp}] Redis memory usage: {used_memory_mb:.2f}MB "
            f"(peak: {used_memory_peak_mb:.2f}MB, RSS: {used_memory_rss_mb:.2f}MB)"
        )

        # Warning thresholds
        warning_threshold_mb = 500  # 500MB
        critical_threshold_mb = 1000  # 1GB

        if used_memory_mb > critical_threshold_mb:
            logger.critical(
                f"[{timestamp}] Redis memory usage is CRITICAL: {used_memory_mb:.2f}MB - "
                "Consider clearing caches or increasing memory"
            )
        elif used_memory_mb > warning_threshold_mb:
            logger.warning(f"[{timestamp}] Redis memory usage is HIGH: {used_memory_mb:.2f}MB")

        # Calculate memory fragmentation ratio
        if "mem_fragmentation_ratio" in info:
            frag_ratio = info["mem_fragmentation_ratio"]
            if frag_ratio > 1.5:
                logger.warning(
                    f"[{timestamp}] Redis memory fragmentation is high: {frag_ratio:.2f}"
                )

        # Get key count
        key_count = client.dbsize()
        logger.info(f"[{timestamp}] Redis key count: {key_count}")

        # Return stats
        return {
            "timestamp": timestamp,
            "used_memory_mb": round(used_memory_mb, 2),
            "used_memory_peak_mb": round(used_memory_peak_mb, 2),
            "used_memory_rss_mb": round(used_memory_rss_mb, 2),
            "fragmentation_ratio": info.get("mem_fragmentation_ratio", 0),
            "key_count": key_count,
        }

    except Exception as e:
        logger.error(f"[{timestamp}] Error monitoring cache size: {str(e)}", exc_info=True)
        return {"error": str(e), "timestamp": timestamp}


@shared_task
def cleanup_expired_sessions():
    """
    Clean up expired Django sessions stored in the cache.

    Django session cleanup is not always automatic when using cache-based sessions.
    This task explicitly removes expired sessions from the cache.

    Returns:
        str: Summary of session cleanup
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Get session cache connection
        session_cache = get_redis_connection("session")

        # Scan for session keys
        session_pattern = "django:session:*"
        cursor = 0
        expired_count = 0

        while True:
            cursor, keys = session_cache.scan(cursor, match=session_pattern)

            for key in keys:
                # If TTL is <= 0, the key has expired or has no expiry
                ttl = session_cache.ttl(key)
                if ttl <= 0:
                    session_cache.delete(key)
                    expired_count += 1

            # Stop when we've scanned all keys
            if cursor == 0:
                break

        logger.info(f"[{timestamp}] Removed {expired_count} expired session keys")
        return f"Removed {expired_count} expired session keys at {timestamp}"

    except Exception as e:
        logger.error(f"[{timestamp}] Error cleaning up sessions: {str(e)}", exc_info=True)
        return f"Error cleaning up sessions: {str(e)}"
