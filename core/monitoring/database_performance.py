"""
Database Performance Monitoring

A utility for monitoring database query performance and identifying slow queries.
"""

import functools
import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

# Thread-local storage for query timing data
_local_storage = threading.local()

# Global collection of slow queries for analysis
_slow_queries: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

# Default threshold for slow query logging (in seconds)
DEFAULT_SLOW_QUERY_THRESHOLD = 0.5


def reset_query_stats():
    """Reset query statistics for the current thread."""
    if hasattr(_local_storage, "query_start_time"):
        del _local_storage.query_start_time
    if hasattr(_local_storage, "query_count"):
        del _local_storage.query_count


def start_query_timer():
    """Start timing database queries for the current request/thread."""
    _local_storage.query_start_time = time.time()
    _local_storage.query_count = len(connection.queries)


def stop_query_timer() -> Optional[Dict[str, Any]]:
    """
    Stop timing database queries and return statistics.

    Returns:
        Dict with query statistics or None if timer wasn't started
    """
    if not hasattr(_local_storage, "query_start_time"):
        return None

    end_time = time.time()
    start_time = _local_storage.query_start_time

    # Calculate time spent in database queries
    new_query_count = len(connection.queries)
    previous_query_count = getattr(_local_storage, "query_count", 0)

    query_count = new_query_count - previous_query_count
    query_time = end_time - start_time

    # Get the new queries
    queries = connection.queries[previous_query_count:new_query_count]

    # Track slow queries for analysis
    slow_query_threshold = getattr(
        settings, "SLOW_QUERY_THRESHOLD", DEFAULT_SLOW_QUERY_THRESHOLD
    )

    slow_queries = []
    total_slow_query_time = 0

    for query in queries:
        query_time_str = query.get("time", "0")
        try:
            query_time_float = float(query_time_str)
            if query_time_float > slow_query_threshold:
                sql = query.get("sql", "")
                slow_queries.append((query_time_float, sql))
                total_slow_query_time += query_time_float

                # Store for global analysis
                if len(_slow_queries[sql]) < 10:  # Limit storage per query
                    _slow_queries[sql].append((query_time_float, time.time()))
        except (ValueError, TypeError):
            pass

    # Log slow queries
    for query_time_float, sql in slow_queries:
        logger.warning(f"Slow query detected: {query_time_float:.3f}s - {sql[:150]}...")

    # Reset for next use
    reset_query_stats()

    return {
        "query_count": query_count,
        "query_time": query_time,
        "avg_query_time": query_time / max(query_count, 1),
        "slow_queries": slow_queries,
        "total_slow_query_time": total_slow_query_time,
    }


def get_slow_query_report(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Generate a report of the slowest queries.

    Args:
        limit: Maximum number of queries to include

    Returns:
        List of query details, ordered by average execution time
    """
    report = []

    for sql, times in _slow_queries.items():
        if not times:
            continue

        avg_time = sum(t[0] for t in times) / len(times)
        max_time = max(t[0] for t in times)
        min_time = min(t[0] for t in times)
        count = len(times)
        last_seen = max(t[1] for t in times)

        report.append(
            {
                "query": sql[:300],  # Truncate for readability
                "avg_time": avg_time,
                "max_time": max_time,
                "min_time": min_time,
                "count": count,
                "last_seen": last_seen,
            }
        )

    # Sort by average time (slowest first)
    report.sort(key=lambda x: x["avg_time"], reverse=True)

    return report[:limit]


def clear_slow_query_history():
    """Clear the collected slow query history."""
    _slow_queries.clear()


def time_query(func):
    """
    Decorator to time database queries in a function.

    Example:
        @time_query
        def get_user_data(user_id):
            # Function that makes database queries
            return User.objects.get(id=user_id)
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Start timing
        start_query_timer()

        try:
            # Execute the function
            result = func(*args, **kwargs)
            return result
        finally:
            # Stop timing and log results
            stats = stop_query_timer()
            if stats and stats["query_count"] > 0:
                logger.info(
                    f"{func.__name__}: {stats['query_count']} queries in "
                    f"{stats['query_time']:.3f}s (avg: {stats['avg_query_time']:.3f}s)"
                )

    return wrapper
