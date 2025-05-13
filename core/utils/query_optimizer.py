"""
Database Query Optimizer

A utility module for identifying, analyzing, and optimizing database queries
in the QueueMe platform. Provides techniques for query profiling, indexing
recommendations, and automatic query optimization.
"""

import functools
import inspect
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db import connection, models, transaction
from django.db.models import Count, F, Q, QuerySet

logger = logging.getLogger(__name__)

# Settings with defaults
QUERY_SAMPLING_RATE = getattr(
    settings, "QUERY_SAMPLING_RATE", 0.1
)  # Sample 10% of queries by default
SLOW_QUERY_THRESHOLD_MS = getattr(
    settings, "SLOW_QUERY_THRESHOLD_MS", 200
)  # Queries taking longer than 200ms are slow
MAX_QUERIES_PER_REQUEST = getattr(
    settings, "MAX_QUERIES_PER_REQUEST", 50
)  # Warning threshold for queries per request
QUERY_LOG_SIZE = getattr(settings, "QUERY_LOG_SIZE", 1000)  # Keep the most recent 1000 slow queries
ENABLE_QUERY_OPTIMIZATION = getattr(
    settings, "ENABLE_QUERY_OPTIMIZATION", True
)  # Auto-optimization is enabled by default


class QueryTracker:
    """
    Tracks database queries, their execution time, and other metrics
    to identify optimization opportunities.
    """

    def __init__(self):
        self.tracked_queries = []
        self.slow_queries = []
        self.optimization_suggestions = {}
        self.query_counts_by_path = {}
        self.query_times_by_path = {}

    @contextmanager
    def track_queries(self, path=None):
        """
        Context manager to track queries within a code block

        Args:
            path: Identifier for this code path (e.g., view name)
        """
        # Save the current query count
        start_queries = len(connection.queries)
        start_time = time.time()

        # Clear the query log to avoid memory buildup in debug mode
        if settings.DEBUG:
            connection.queries_log.clear()

        try:
            # Execute the code block
            yield
        finally:
            # If we're in debug mode, analyze the queries
            if settings.DEBUG:
                end_time = time.time()
                end_queries = len(connection.queries)
                duration_ms = (end_time - start_time) * 1000
                query_count = end_queries - start_queries

                # Log if this path generates a lot of queries
                if path and query_count > 0:
                    if path not in self.query_counts_by_path:
                        self.query_counts_by_path[path] = []
                    if path not in self.query_times_by_path:
                        self.query_times_by_path[path] = []

                    self.query_counts_by_path[path].append(query_count)
                    self.query_times_by_path[path].append(duration_ms)

                    # Keep the lists from growing too large
                    if len(self.query_counts_by_path[path]) > 100:
                        self.query_counts_by_path[path].pop(0)
                        self.query_times_by_path[path].pop(0)

                # Analyze individual queries
                queries = connection.queries[start_queries:end_queries]
                for query_info in queries:
                    self._analyze_query(query_info, path)

                # Log excessive queries
                if query_count > MAX_QUERIES_PER_REQUEST:
                    logger.warning(
                        f"Excessive database queries: {query_count} queries in {path or 'unknown path'} "
                        f"taking {duration_ms:.2f}ms"
                    )

    def _analyze_query(self, query_info, path=None):
        """
        Analyze a single query for performance issues

        Args:
            query_info: Dictionary with query information
            path: Identifier for code path that generated the query
        """
        sql = query_info.get("sql", "")
        duration_ms = float(query_info.get("time", 0)) * 1000

        # Track slow queries
        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            self._record_slow_query(sql, duration_ms, path)

        # Check for common issues
        if "SELECT" in sql and "WHERE" not in sql and "LIMIT" not in sql:
            self._add_suggestion(sql, "Consider adding filters or limits to avoid full table scans")

        if "SELECT *" in sql:
            self._add_suggestion(sql, "Select only needed columns instead of using SELECT *")

        if "WHERE" in sql and "LIKE" in sql and sql.count("%") > 0 and "LIKE '%%'" in sql:
            self._add_suggestion(sql, "Leading wildcard LIKE filters are inefficient for indexing")

        if "COUNT(*)" in sql and "GROUP BY" in sql:
            self._add_suggestion(
                sql,
                "Consider using annotate(count=Count('field')) for counting related objects",
            )

        if "JOIN" in sql and sql.count("JOIN") > 2:
            self._add_suggestion(
                sql,
                "Multiple JOINs may be inefficient, consider select_related/prefetch_related",
            )

        self.tracked_queries.append(
            {
                "sql": sql,
                "duration_ms": duration_ms,
                "path": path,
                "timestamp": time.time(),
            }
        )

    def _record_slow_query(self, sql, duration_ms, path=None):
        """
        Record information about a slow query

        Args:
            sql: SQL query string
            duration_ms: Query duration in milliseconds
            path: Code path that generated the query
        """
        self.slow_queries.append(
            {
                "sql": sql,
                "duration_ms": duration_ms,
                "path": path,
                "timestamp": time.time(),
            }
        )

        # Keep the slow query list from growing too large
        if len(self.slow_queries) > QUERY_LOG_SIZE:
            self.slow_queries.pop(0)

        # Log slow queries
        logger.warning(
            f"Slow query detected ({duration_ms:.2f}ms) in {path or 'unknown path'}: {sql[:200]}..."
        )

    def _add_suggestion(self, sql, suggestion):
        """
        Add an optimization suggestion for a query

        Args:
            sql: SQL query string
            suggestion: Optimization suggestion
        """
        if sql not in self.optimization_suggestions:
            self.optimization_suggestions[sql] = []

        if suggestion not in self.optimization_suggestions[sql]:
            self.optimization_suggestions[sql].append(suggestion)

    def get_slow_query_report(self) -> Dict[str, Any]:
        """
        Generate a report of slow queries and optimization opportunities

        Returns:
            Dictionary with slow query statistics
        """
        # Calculate stats
        total_slow_queries = len(self.slow_queries)

        if total_slow_queries == 0:
            return {
                "total_slow_queries": 0,
                "paths_with_slow_queries": [],
                "top_slowest_queries": [],
                "optimization_suggestions": [],
            }

        # Group slow queries by path
        paths_with_slow_queries = {}
        for query in self.slow_queries:
            path = query.get("path") or "unknown"
            if path not in paths_with_slow_queries:
                paths_with_slow_queries[path] = {
                    "count": 0,
                    "total_duration_ms": 0,
                    "avg_duration_ms": 0,
                }

            paths_with_slow_queries[path]["count"] += 1
            paths_with_slow_queries[path]["total_duration_ms"] += query["duration_ms"]

        # Calculate averages
        for path_stats in paths_with_slow_queries.values():
            path_stats["avg_duration_ms"] = path_stats["total_duration_ms"] / path_stats["count"]

        # Get top slowest queries
        top_slowest = sorted(self.slow_queries, key=lambda q: q["duration_ms"], reverse=True)[:10]

        # Format optimization suggestions
        formatted_suggestions = []
        for sql, suggestions in self.optimization_suggestions.items():
            formatted_suggestions.append(
                {
                    "sql": sql[:200] + ("..." if len(sql) > 200 else ""),
                    "suggestions": suggestions,
                }
            )

        return {
            "total_slow_queries": total_slow_queries,
            "paths_with_slow_queries": [
                {
                    "path": path,
                    "count": stats["count"],
                    "avg_duration_ms": stats["avg_duration_ms"],
                    "total_duration_ms": stats["total_duration_ms"],
                }
                for path, stats in sorted(
                    paths_with_slow_queries.items(),
                    key=lambda item: item[1]["total_duration_ms"],
                    reverse=True,
                )
            ],
            "top_slowest_queries": [
                {
                    "sql": query["sql"][:200] + ("..." if len(query["sql"]) > 200 else ""),
                    "duration_ms": query["duration_ms"],
                    "path": query["path"] or "unknown",
                }
                for query in top_slowest
            ],
            "optimization_suggestions": formatted_suggestions,
        }

    def get_query_stats_by_path(self) -> Dict[str, Any]:
        """
        Get query statistics grouped by code path

        Returns:
            Dictionary with query statistics by path
        """
        stats_by_path = {}

        for path, counts in self.query_counts_by_path.items():
            times = self.query_times_by_path.get(path, [])

            if not counts or not times:
                continue

            avg_count = sum(counts) / len(counts)
            avg_time = sum(times) / len(times)

            stats_by_path[path] = {
                "avg_query_count": avg_count,
                "avg_total_time_ms": avg_time,
                "avg_time_per_query_ms": avg_time / avg_count if avg_count > 0 else 0,
                "samples": len(counts),
            }

        return stats_by_path

    def reset_stats(self):
        """Reset all statistics"""
        self.tracked_queries = []
        self.slow_queries = []
        self.optimization_suggestions = {}
        self.query_counts_by_path = {}
        self.query_times_by_path = {}


# Create a global tracker instance
query_tracker = QueryTracker()


def track_queries(path=None):
    """
    Decorator to track queries in a function

    Args:
        path: Identifier for this code path
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_path = path or f"{func.__module__}.{func.__name__}"
            with query_tracker.track_queries(func_path):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def analyze_queryset(queryset: QuerySet) -> Dict[str, Any]:
    """
    Analyze a queryset for potential optimizations

    Args:
        queryset: Django QuerySet to analyze

    Returns:
        Dictionary with optimization suggestions
    """
    suggestions = []
    query_info = {}

    try:
        # Get model info
        model = queryset.model
        query_info["model"] = model.__name__

        # Check if queryset is evaluated
        query_info["is_evaluated"] = queryset._result_cache is not None

        # Check for select_related opportunities
        foreign_key_fields = []
        for field in model._meta.fields:
            if isinstance(field, models.ForeignKey):
                foreign_key_fields.append(field.name)

        if foreign_key_fields:
            current_select_related = queryset.query.select_related
            if not current_select_related:
                suggestions.append(
                    {
                        "type": "select_related",
                        "message": f"Consider using select_related for these ForeignKey fields: {', '.join(foreign_key_fields)}",
                    }
                )
            else:
                missing_fields = [f for f in foreign_key_fields if f not in current_select_related]
                if missing_fields:
                    suggestions.append(
                        {
                            "type": "select_related",
                            "message": f"Consider adding these fields to select_related: {', '.join(missing_fields)}",
                        }
                    )

        # Check for prefetch_related opportunities
        m2m_fields = []
        for field in model._meta.many_to_many:
            m2m_fields.append(field.name)

        reverse_relations = [
            f.name for f in model._meta.related_objects if f.related_model and f.field.many_to_many
        ]

        potential_prefetch_fields = m2m_fields + reverse_relations

        if potential_prefetch_fields:
            current_prefetch_related = getattr(queryset, "_prefetch_related_lookups", [])
            missing_prefetch = [
                f for f in potential_prefetch_fields if f not in current_prefetch_related
            ]

            if missing_prefetch:
                suggestions.append(
                    {
                        "type": "prefetch_related",
                        "message": f"Consider using prefetch_related for these fields: {', '.join(missing_prefetch)}",
                    }
                )

        # Check for non-indexed filters
        if hasattr(queryset, "query") and hasattr(queryset.query, "where"):
            where_clause = str(queryset.query.where)
            query_info["has_where_clause"] = where_clause != "OR ()"

            # Basic check for potential non-indexed fields
            filter_fields = [
                name.split("__")[0] for name in queryset.query.annotations.keys() if "__" in name
            ]

            indexed_fields = _get_indexed_fields(model)
            non_indexed_filters = [f for f in filter_fields if f not in indexed_fields]

            if non_indexed_filters:
                suggestions.append(
                    {
                        "type": "missing_index",
                        "message": f"These filter fields may need indexes: {', '.join(non_indexed_filters)}",
                    }
                )

        # Check for excessive limit/offset
        query_info["has_slicing"] = False
        if hasattr(queryset, "query"):
            has_high_offset = queryset.query.low_mark and queryset.query.low_mark > 1000
            query_info["has_slicing"] = (
                queryset.query.low_mark is not None or queryset.query.high_mark is not None
            )

            if has_high_offset:
                suggestions.append(
                    {
                        "type": "high_offset",
                        "message": f"High offset detected ({queryset.query.low_mark}). Consider using keyset pagination instead.",
                    }
                )

        # Get the SQL for reference
        query_info["sql"] = str(queryset.query)

    except Exception as e:
        return {"error": str(e), "suggestions": []}

    return {"query_info": query_info, "suggestions": suggestions}


def optimize_queryset(queryset: QuerySet) -> QuerySet:
    """
    Automatically apply common optimizations to a queryset

    Args:
        queryset: QuerySet to optimize

    Returns:
        Optimized QuerySet
    """
    if not ENABLE_QUERY_OPTIMIZATION:
        return queryset

    model = queryset.model
    optimized = queryset

    # Add select_related for foreign keys if not already present
    fk_fields = []
    for field in model._meta.fields:
        if isinstance(field, models.ForeignKey):
            fk_fields.append(field.name)

    current_select_related = queryset.query.select_related
    if fk_fields and not current_select_related:
        # Only select_related if there are <= 5 foreign keys to avoid over-fetching
        if len(fk_fields) <= 5:
            optimized = optimized.select_related(*fk_fields)

    # Don't automatically add prefetch_related as it's more complex
    # and might lead to unexpected performance issues if applied incorrectly

    return optimized


def suggest_indexes(model_class) -> List[Dict[str, Any]]:
    """
    Suggest indexes for a model based on its usage patterns

    Args:
        model_class: Django model class

    Returns:
        List of index suggestions
    """
    suggestions = []

    # Get existing indexes
    existing_indexes = _get_indexed_fields(model_class)

    # Check common fields that should be indexed
    fields_to_check = [(field, [field.name]) for field in model_class._meta.fields]

    for field, field_names in fields_to_check:
        for field_name in field_names:
            # Skip if already indexed
            if field_name in existing_indexes:
                continue

            # Foreign keys should usually be indexed
            if isinstance(field, models.ForeignKey):
                suggestions.append(
                    {
                        "field": field_name,
                        "reason": "Foreign key field that should be indexed for faster joins",
                    }
                )

            # Fields commonly used in filters should be indexed
            elif field_name in ["created_at", "updated_at", "status", "is_active"]:
                suggestions.append(
                    {
                        "field": field_name,
                        "reason": f"Common filter field '{field_name}' that should be indexed",
                    }
                )

            # Fields with 'slug' in name should be indexed
            elif "slug" in field_name:
                suggestions.append(
                    {
                        "field": field_name,
                        "reason": "Slug field used for lookups should be indexed",
                    }
                )

    return suggestions


def _get_indexed_fields(model_class) -> List[str]:
    """
    Get a list of indexed fields for a model

    Args:
        model_class: Django model class

    Returns:
        List of field names that are indexed
    """
    indexed_fields = []

    # Get indexes from model meta
    for index in model_class._meta.indexes:
        if hasattr(index, "fields"):
            for field_name in index.fields:
                # Strip ordering indicators (e.g., '-created_at')
                clean_name = field_name[1:] if field_name.startswith("-") else field_name
                indexed_fields.append(clean_name)

    # Primary key is always indexed
    pk_name = model_class._meta.pk.name
    indexed_fields.append(pk_name)

    # Unique fields are indexed
    for field in model_class._meta.fields:
        if field.unique and field.name != pk_name:
            indexed_fields.append(field.name)

    # Foreign keys usually have indexes
    for field in model_class._meta.fields:
        if isinstance(field, models.ForeignKey) and field.name not in indexed_fields:
            indexed_fields.append(field.name)

    return indexed_fields


@contextmanager
def query_explain():
    """
    Context manager to run EXPLAIN on queries
    """
    explain_queries = []
    real_execute = connection.cursor().execute

    def explain_execute(self, sql, params=None):
        if sql.strip().upper().startswith("SELECT"):
            explain_sql = f"EXPLAIN {sql}"
            explain_cursor = connection.cursor()
            try:
                explain_cursor.execute(explain_sql, params)
                explain_result = explain_cursor.fetchall()
                explain_queries.append({"sql": sql, "explain": explain_result})
            except Exception as e:
                logger.error(f"Error executing EXPLAIN: {e}")
            finally:
                explain_cursor.close()

        return real_execute(sql, params)

    # Patch the execute method
    connection.cursor().execute = explain_execute

    try:
        yield explain_queries
    finally:
        # Restore original method
        connection.cursor().execute = real_execute


def get_index_usage_stats(connection=None):
    """
    Get index usage statistics from PostgreSQL

    Args:
        connection: Database connection (optional)

    Returns:
        Dictionary with index usage statistics
    """
    if not connection:
        connection = connection

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.schemaname,
                    s.relname AS tablename,
                    s.indexrelname AS indexname,
                    pg_relation_size(s.indexrelid) AS index_size,
                    s.idx_scan AS index_scans,
                    s.idx_tup_read AS tuples_read,
                    s.idx_tup_fetch AS tuples_fetched
                FROM pg_catalog.pg_stat_user_indexes s
                JOIN pg_catalog.pg_index i ON s.indexrelid = i.indexrelid
                WHERE s.idx_scan > 0
                ORDER BY s.idx_scan DESC, pg_relation_size(s.indexrelid) DESC;
            """
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "size_bytes": row[3],
                        "scans": row[4],
                        "tuples_read": row[5],
                        "tuples_fetched": row[6],
                    }
                )

            # Also get unused indexes
            cursor.execute(
                """
                SELECT
                    s.schemaname,
                    s.relname AS tablename,
                    s.indexrelname AS indexname,
                    pg_relation_size(s.indexrelid) AS index_size
                FROM pg_catalog.pg_stat_user_indexes s
                JOIN pg_catalog.pg_index i ON s.indexrelid = i.indexrelid
                WHERE s.idx_scan = 0 AND NOT i.indisprimary
                ORDER BY pg_relation_size(s.indexrelid) DESC;
            """
            )

            unused_indexes = []
            for row in cursor.fetchall():
                unused_indexes.append(
                    {
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "size_bytes": row[3],
                    }
                )

            return {"used_indexes": results, "unused_indexes": unused_indexes}
    except Exception as e:
        logger.error(f"Error getting index usage stats: {e}")
        return {"error": str(e), "used_indexes": [], "unused_indexes": []}


class CachingQuerySetMixin:
    """
    Mixin to add caching capabilities to QuerySets
    """

    def cached(self, timeout=60 * 10, key_prefix=None):
        """
        Cache the queryset results

        Args:
            timeout: Cache timeout in seconds
            key_prefix: Optional prefix for cache key

        Returns:
            Queryset with caching
        """
        clone = self._clone()
        clone._add_cached_behavior(timeout, key_prefix)
        return clone

    def _add_cached_behavior(self, timeout, key_prefix):
        """
        Add caching behavior to the queryset

        Args:
            timeout: Cache timeout
            key_prefix: Cache key prefix
        """
        # Store original iterator method
        original_iterator = self._iterator

        def cached_iterator():
            # Generate cache key
            query_str = str(self.query)
            cache_key = f"queryset:{key_prefix or self.model.__name__}:{hash(query_str)}"

            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return iter(cached_result)

            # Get results and cache them
            result = list(original_iterator())
            cache.set(cache_key, result, timeout)
            return iter(result)

        # Replace iterator method
        self._iterator = cached_iterator


# Global functions for easier access
track_slow_queries = query_tracker.track_queries
get_slow_query_report = query_tracker.get_slow_query_report
get_query_stats = query_tracker.get_query_stats_by_path
reset_query_stats = query_tracker.reset_stats
