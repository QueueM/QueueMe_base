#!/usr/bin/env python
"""
QueueMe Health Check System

Monitors critical system components and returns health status:
1. Database connectivity
2. Redis connectivity
3. External API integration status
4. Celery worker status
5. Disk space usage
6. System load and memory usage
"""

import argparse
import datetime
import json
import logging
import os
import socket
import sys
import time
from io import StringIO
from urllib.parse import urlparse

import psutil
import requests

# Add project to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(PROJECT_DIR, "logs", "health_check.log")),
    ],
)
logger = logging.getLogger("health_check")

# Set Django settings module for Django-specific checks
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")


def check_database():
    """
    Check database connectivity and performance

    Returns:
        Dictionary with database health status
    """
    try:
        import django

        django.setup()
        from django.db import connections
        from django.db.utils import OperationalError

        db_results = {}

        # Check each configured database
        for alias in connections:
            start_time = time.time()
            try:
                # Try to get cursor and execute simple query
                connection = connections[alias]
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()

                # Calculate query time
                query_time = time.time() - start_time

                # Get connection info
                db_info = connections.databases[alias]
                db_engine = db_info.get("ENGINE", "").split(".")[-1]

                # Get more detailed stats for PostgreSQL
                if db_engine == "postgresql":
                    cursor.execute(
                        """
                        SELECT
                            pg_database_size(current_database()) as db_size,
                            (SELECT count(*) FROM pg_stat_activity) as connections,
                            extract(epoch from current_timestamp - pg_postmaster_start_time()) as uptime
                    """
                    )
                    stats = cursor.fetchone()

                    db_results[alias] = {
                        "status": "healthy",
                        "response_time": round(query_time * 1000, 2),  # ms
                        "engine": db_engine,
                        "size_mb": round(stats[0] / (1024 * 1024), 2),
                        "connections": stats[1],
                        "uptime_hours": round(stats[2] / 3600, 2),
                    }
                else:
                    db_results[alias] = {
                        "status": "healthy",
                        "response_time": round(query_time * 1000, 2),  # ms
                        "engine": db_engine,
                    }

            except OperationalError as e:
                db_results[alias] = {
                    "status": "error",
                    "error": str(e),
                    "engine": db_info.get("ENGINE", "").split(".")[-1],
                }
            except Exception as e:
                db_results[alias] = {
                    "status": "error",
                    "error": f"Unexpected error: {str(e)}",
                }

        return {
            "status": (
                "healthy"
                if all(db["status"] == "healthy" for db in db_results.values())
                else "unhealthy"
            ),
            "databases": db_results,
        }

    except Exception as e:
        logger.error(f"Database check error: {str(e)}")
        return {"status": "error", "error": str(e)}


def check_redis():
    """
    Check Redis connectivity and performance

    Returns:
        Dictionary with Redis health status
    """
    try:
        import django
        import redis

        django.setup()
        from django.conf import settings

        redis_results = {}

        # Get Redis URLs from settings
        redis_urls = []

        # Main Redis URL
        if hasattr(settings, "REDIS_URL"):
            redis_urls.append(("default", settings.REDIS_URL))

        # Celery Redis URL
        if (
            hasattr(settings, "CELERY_BROKER_URL")
            and "redis://" in settings.CELERY_BROKER_URL
        ):
            redis_urls.append(("celery", settings.CELERY_BROKER_URL))

        # Cache Redis URL
        if hasattr(settings, "CACHES") and "RedisCache" in settings.CACHES.get(
            "default", {}
        ).get("BACKEND", ""):
            redis_cache_url = settings.CACHES["default"].get("LOCATION", "")
            if isinstance(redis_cache_url, list):
                redis_cache_url = redis_cache_url[0]
            redis_urls.append(("cache", redis_cache_url))

        # Channel layers Redis URL
        if hasattr(
            settings, "CHANNEL_LAYERS"
        ) and "RedisChannelLayer" in settings.CHANNEL_LAYERS.get("default", {}).get(
            "BACKEND", ""
        ):
            config = settings.CHANNEL_LAYERS["default"].get("CONFIG", {})
            if "hosts" in config:
                host = config["hosts"][0]
                if isinstance(host, list):
                    redis_channel_url = f"redis://{host[0]}:{host[1]}"
                    redis_urls.append(("channels", redis_channel_url))

        # Check each Redis instance
        for alias, url in redis_urls:
            start_time = time.time()
            try:
                # Parse URL and create Redis client
                parsed_url = urlparse(url)
                host = parsed_url.hostname or "localhost"
                port = parsed_url.port or 6379
                db = int(parsed_url.path.replace("/", "") or 0)

                r = redis.Redis(host=host, port=port, db=db, socket_timeout=5)

                # Ping and measure response time
                r.ping()
                ping_time = time.time() - start_time

                # Get Redis info
                info = r.info()

                redis_results[alias] = {
                    "status": "healthy",
                    "response_time": round(ping_time * 1000, 2),  # ms
                    "version": info.get("redis_version"),
                    "memory_used_mb": round(
                        info.get("used_memory", 0) / (1024 * 1024), 2
                    ),
                    "clients_connected": info.get("connected_clients"),
                    "uptime_days": round(
                        info.get("uptime_in_seconds", 0) / (24 * 3600), 2
                    ),
                }

            except Exception as e:
                redis_results[alias] = {"status": "error", "error": str(e)}

        return {
            "status": (
                "healthy"
                if all(r["status"] == "healthy" for r in redis_results.values())
                else "unhealthy"
            ),
            "instances": redis_results,
        }

    except Exception as e:
        logger.error(f"Redis check error: {str(e)}")
        return {"status": "error", "error": str(e)}


def check_celery():
    """
    Check Celery worker status

    Returns:
        Dictionary with Celery health status
    """
    try:
        import subprocess

        # Run celery inspect ping command
        result = subprocess.run(
            ["celery", "-A", "queueme", "inspect", "ping"],
            capture_output=True,
            text=True,
            timeout=10,  # timeout after 10 seconds
        )

        # Parse output to determine if workers are running
        output = result.stdout

        if "No nodes replied within time constraint" in output or not output:
            return {"status": "unhealthy", "error": "No Celery workers responded"}

        if "pong" in output.lower():
            # Extract active workers
            workers = []
            current_worker = None
            for line in output.splitlines():
                if "-> " in line and "celery@" in line:
                    current_worker = line.strip().split("-> ")[1].strip(":")
                elif current_worker and "OK" in line:
                    workers.append(current_worker)

            # Check task queue stats
            stats_result = subprocess.run(
                ["celery", "-A", "queueme", "inspect", "stats"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            worker_stats = {}
            current_worker = None

            for line in stats_result.stdout.splitlines():
                if "-> " in line and "celery@" in line:
                    current_worker = line.strip().split("-> ")[1].strip(":")
                    worker_stats[current_worker] = {}
                elif current_worker:
                    if line.strip().startswith(
                        ("prefetch_count:", "pool:", "processed:")
                    ):
                        key, value = line.strip().split(":", 1)
                        worker_stats[current_worker][key.strip()] = value.strip()

            return {
                "status": "healthy",
                "workers": workers,
                "worker_count": len(workers),
                "stats": worker_stats,
            }
        else:
            return {
                "status": "unhealthy",
                "error": "Celery workers not responding properly",
                "output": output,
            }

    except subprocess.TimeoutExpired:
        logger.error("Celery check timed out")
        return {"status": "error", "error": "Celery command timed out"}
    except Exception as e:
        logger.error(f"Celery check error: {str(e)}")
        return {"status": "error", "error": str(e)}


def check_integrations():
    """
    Check external integrations status

    Returns:
        Dictionary with integrations health status
    """
    integrations = {}

    # Check Moyasar payment gateway
    try:
        import django

        django.setup()
        from django.conf import settings

        moyasar_key = getattr(settings, "MOYASAR_API_KEY", None)

        if moyasar_key:
            # Make a test request to Moyasar API
            url = "https://api.moyasar.com/v1/payments"
            headers = {"Authorization": f"Basic {moyasar_key}"}

            start_time = time.time()
            response = requests.get(
                url, headers=headers, params={"limit": 1}, timeout=10
            )

            response_time = time.time() - start_time

            if response.status_code == 200:
                integrations["moyasar"] = {
                    "status": "healthy",
                    "response_time": round(response_time * 1000, 2),  # ms
                    "api_version": "v1",
                }
            else:
                integrations["moyasar"] = {
                    "status": "error",
                    "error": f"API returned status code {response.status_code}",
                    "response_time": round(response_time * 1000, 2),  # ms
                }
        else:
            integrations["moyasar"] = {
                "status": "not_configured",
                "error": "Moyasar API key not configured",
            }

    except Exception as e:
        integrations["moyasar"] = {"status": "error", "error": str(e)}

    # Check Firebase integration
    try:
        firebase_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)

        if firebase_path and os.path.exists(firebase_path):
            integrations["firebase"] = {
                "status": "configured",
                "credentials_file": os.path.basename(firebase_path),
                "file_exists": True,
            }
        else:
            integrations["firebase"] = {
                "status": "not_configured",
                "error": f"Firebase credentials file not found: {firebase_path}",
            }
    except Exception as e:
        integrations["firebase"] = {"status": "error", "error": str(e)}

    # Check Twilio integration
    try:
        twilio_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        twilio_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)

        if twilio_sid and twilio_token:
            # We don't make an actual API call to avoid potential charges
            integrations["twilio"] = {
                "status": "configured",
                "account_sid": f"{twilio_sid[:4]}...{twilio_sid[-4:]}",
            }
        else:
            integrations["twilio"] = {
                "status": "not_configured",
                "error": "Twilio credentials not configured",
            }
    except Exception as e:
        integrations["twilio"] = {"status": "error", "error": str(e)}

    return {
        "status": (
            "healthy"
            if all(
                i["status"] in ("healthy", "configured") for i in integrations.values()
            )
            else "unhealthy"
        ),
        "integrations": integrations,
    }


def check_system():
    """
    Check system resources

    Returns:
        Dictionary with system health status
    """
    try:
        # CPU usage and load
        cpu_percent = psutil.cpu_percent(interval=1)
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0]

        # Memory usage
        memory = psutil.virtual_memory()

        # Disk usage
        disk = psutil.disk_usage("/")

        # Check if any resource is critically low
        critical = False
        warnings = []

        if cpu_percent > 90:
            critical = True
            warnings.append(f"CPU usage is critical: {cpu_percent}%")

        if memory.percent > 90:
            critical = True
            warnings.append(f"Memory usage is critical: {memory.percent}%")

        if disk.percent > 90:
            critical = True
            warnings.append(f"Disk usage is critical: {disk.percent}%")

        return {
            "status": "unhealthy" if critical else "healthy",
            "warnings": warnings,
            "cpu": {
                "usage_percent": cpu_percent,
                "load_avg_1min": load_avg[0],
                "load_avg_5min": load_avg[1],
                "load_avg_15min": load_avg[2],
                "cores": psutil.cpu_count(),
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent,
            },
        }
    except Exception as e:
        logger.error(f"System check error: {str(e)}")
        return {"status": "error", "error": str(e)}


def check_queue_app():
    """
    Check QueueMe application specific health

    Returns:
        Dictionary with application health
    """
    try:
        import django

        django.setup()
        import datetime

        from django.db import connection
        from django.utils import timezone

        results = {}

        # Get active queue count
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM queueapp_queueticket
                WHERE status = 'waiting' AND created_at > %s
            """,
                [timezone.now() - datetime.timedelta(days=1)],
            )
            active_queue_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM bookingapp_appointment
                WHERE status = 'confirmed' AND date >= %s
            """,
                [timezone.now().date()],
            )
            today_appointments = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM authapp_user
                WHERE is_active = TRUE
            """
            )
            active_users = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM payment_paymenttransaction
                WHERE created_at > %s AND status = 'completed'
            """,
                [timezone.now() - datetime.timedelta(days=1)],
            )
            recent_transactions = cursor.fetchone()[0]

        results = {
            "status": "healthy",
            "active_queue_tickets": active_queue_count,
            "todays_appointments": today_appointments,
            "active_users": active_users,
            "recent_transactions": recent_transactions,
        }

        return results
    except Exception as e:
        logger.error(f"Queue app check error: {str(e)}")
        return {"status": "error", "error": str(e)}


def perform_health_check(output_format="json"):
    """
    Perform complete health check of all components

    Args:
        output_format: Format to output results (json or text)

    Returns:
        Health check results in specified format
    """
    health_results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "summary": "healthy",
        "checks": {},
    }

    # Database check
    health_results["checks"]["database"] = check_database()

    # Redis check
    health_results["checks"]["redis"] = check_redis()

    # Celery check
    health_results["checks"]["celery"] = check_celery()

    # External integrations check
    health_results["checks"]["integrations"] = check_integrations()

    # System resources check
    health_results["checks"]["system"] = check_system()

    # QueueMe app specific check
    health_results["checks"]["queueme_app"] = check_queue_app()

    # Determine overall health
    checks_status = [check["status"] for check in health_results["checks"].values()]
    if "error" in checks_status or "unhealthy" in checks_status:
        health_results["summary"] = "unhealthy"

    if output_format == "json":
        return json.dumps(health_results, indent=2)
    else:
        # Generate text report
        output = StringIO()

        output.write("=== QueueMe Health Check Report ===\n")
        output.write(f"Timestamp: {health_results['timestamp']}\n")
        output.write(f"Hostname: {health_results['hostname']}\n")
        output.write(f"Overall Status: {health_results['summary'].upper()}\n\n")

        for check_name, check_result in health_results["checks"].items():
            output.write(f"== {check_name.upper()} ==\n")
            output.write(f"Status: {check_result['status'].upper()}\n")

            if check_result["status"] == "error" and "error" in check_result:
                output.write(f"Error: {check_result['error']}\n")

            if check_name == "database" and "databases" in check_result:
                for db_name, db_info in check_result["databases"].items():
                    output.write(f"Database {db_name}: {db_info['status']}\n")
                    if "response_time" in db_info:
                        output.write(
                            f"  Response Time: {db_info['response_time']} ms\n"
                        )
                    if "error" in db_info:
                        output.write(f"  Error: {db_info['error']}\n")

            if check_name == "redis" and "instances" in check_result:
                for redis_name, redis_info in check_result["instances"].items():
                    output.write(f"Redis {redis_name}: {redis_info['status']}\n")
                    if "response_time" in redis_info:
                        output.write(
                            f"  Response Time: {redis_info['response_time']} ms\n"
                        )
                    if "error" in redis_info:
                        output.write(f"  Error: {redis_info['error']}\n")

            if check_name == "celery" and check_result["status"] == "healthy":
                output.write(f"Workers: {check_result.get('worker_count', 0)}\n")

            if check_name == "system":
                if "cpu" in check_result:
                    output.write(
                        f"CPU Usage: {check_result['cpu']['usage_percent']}%\n"
                    )
                if "memory" in check_result:
                    output.write(
                        f"Memory Usage: {check_result['memory']['percent']}%\n"
                    )
                if "disk" in check_result:
                    output.write(f"Disk Usage: {check_result['disk']['percent']}%\n")
                if "warnings" in check_result and check_result["warnings"]:
                    output.write("Warnings:\n")
                    for warning in check_result["warnings"]:
                        output.write(f"  - {warning}\n")

            if check_name == "queueme_app":
                if "active_queue_tickets" in check_result:
                    output.write(
                        f"Active Queue Tickets: {check_result['active_queue_tickets']}\n"
                    )
                if "todays_appointments" in check_result:
                    output.write(
                        f"Today's Appointments: {check_result['todays_appointments']}\n"
                    )

            output.write("\n")

        return output.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QueueMe Health Check")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    health_check_result = perform_health_check(args.format)

    if args.output:
        with open(args.output, "w") as f:
            f.write(health_check_result)
    else:
        print(health_check_result)
