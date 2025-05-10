"""
Prometheus metrics for Queue Me platform.

This module defines all Prometheus metrics used for monitoring the application.
"""

from prometheus_client import Counter, Histogram, Gauge

# Task metrics
TASK_DURATION_SECONDS = Histogram(
    'task_duration_seconds',
    'Time spent processing tasks',
    ['task_name', 'status']
)

TASK_FAILURES_TOTAL = Counter(
    'task_failures_total',
    'Total number of task failures',
    ['task_name', 'error_type']
)

TASK_RETRIES_TOTAL = Counter(
    'task_retries_total',
    'Total number of task retries',
    ['task_name', 'error_type']
)

# Database metrics
DB_CONNECTION_ERRORS_TOTAL = Counter(
    'db_connection_errors_total',
    'Total number of database connection errors'
)

DB_QUERY_DURATION_SECONDS = Histogram(
    'db_query_duration_seconds',
    'Time spent executing database queries',
    ['query_type']
)

# API metrics
API_REQUEST_DURATION_SECONDS = Histogram(
    'api_request_duration_seconds',
    'Time spent processing API requests',
    ['method', 'endpoint', 'status']
)

API_REQUESTS_TOTAL = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

# Cache metrics
CACHE_HITS_TOTAL = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_name']
)

CACHE_MISSES_TOTAL = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_name']
)

# WebSocket metrics
WEBSOCKET_CONNECTIONS_TOTAL = Counter(
    'websocket_connections_total',
    'Total number of WebSocket connections',
    ['connection_type', 'status']
)

WEBSOCKET_MESSAGES_TOTAL = Counter(
    'websocket_messages_total',
    'Total number of WebSocket messages',
    ['connection_type', 'message_type']
)

# Queue metrics
QUEUE_TICKETS_TOTAL = Gauge(
    'queue_tickets_total',
    'Total number of tickets in queue',
    ['queue_id', 'status']
)

QUEUE_WAIT_TIME_SECONDS = Histogram(
    'queue_wait_time_seconds',
    'Time spent waiting in queue',
    ['queue_id']
)

# Authentication metrics
AUTH_ATTEMPTS_TOTAL = Counter(
    'auth_attempts_total',
    'Total number of authentication attempts',
    ['method', 'status']
)

AUTH_FAILURES_TOTAL = Counter(
    'auth_failures_total',
    'Total number of authentication failures',
    ['method', 'reason']
)

# Rate limiting metrics
RATE_LIMIT_HITS_TOTAL = Counter(
    'rate_limit_hits_total',
    'Total number of rate limit hits',
    ['action_type', 'status']
)

# Media processing metrics
MEDIA_PROCESSING_DURATION_SECONDS = Histogram(
    'media_processing_duration_seconds',
    'Time spent processing media files',
    ['media_type', 'operation']
)

MEDIA_PROCESSING_ERRORS_TOTAL = Counter(
    'media_processing_errors_total',
    'Total number of media processing errors',
    ['media_type', 'error_type']
)

# System metrics
SYSTEM_MEMORY_USAGE_BYTES = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_CPU_USAGE_PERCENT = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_DISK_USAGE_BYTES = Gauge(
    'system_disk_usage_bytes',
    'System disk usage in bytes'
) 