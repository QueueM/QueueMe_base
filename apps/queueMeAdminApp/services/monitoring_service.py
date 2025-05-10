import logging
import time

import psutil
from django.db import connection
from django.db.utils import OperationalError
from django.utils import timezone

from ..constants import (
    MAINTENANCE_CANCELLED,
    PLATFORM_STATUS_CHOICES,
    PLATFORM_STATUS_DEGRADED,
    PLATFORM_STATUS_MAJOR_OUTAGE,
    PLATFORM_STATUS_OPERATIONAL,
    PLATFORM_STATUS_PARTIAL_OUTAGE,
)
from ..models import MaintenanceSchedule, PlatformStatus

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Service for monitoring system health and performance.
    """

    @staticmethod
    def get_overall_status():
        """
        Get overall platform status summary.

        Returns:
            dict: Overall platform status
        """
        # Get all component statuses
        component_statuses = PlatformStatus.objects.all()

        # Default to operational if no components exist
        if not component_statuses.exists():
            return {
                "status": PLATFORM_STATUS_OPERATIONAL,
                "message": "All systems operational",
                "last_updated": timezone.now().isoformat(),
                "components": [],
            }

        # Determine overall status based on component statuses
        has_major_outage = component_statuses.filter(
            status=PLATFORM_STATUS_MAJOR_OUTAGE
        ).exists()
        has_partial_outage = component_statuses.filter(
            status=PLATFORM_STATUS_PARTIAL_OUTAGE
        ).exists()
        has_degraded = component_statuses.filter(
            status=PLATFORM_STATUS_DEGRADED
        ).exists()

        if has_major_outage:
            overall_status = PLATFORM_STATUS_MAJOR_OUTAGE
            message = "Major system outage detected"
        elif has_partial_outage:
            overall_status = PLATFORM_STATUS_PARTIAL_OUTAGE
            message = "Partial system outage detected"
        elif has_degraded:
            overall_status = PLATFORM_STATUS_DEGRADED
            message = "System performance is degraded"
        else:
            overall_status = PLATFORM_STATUS_OPERATIONAL
            message = "All systems operational"

        # Get most recent update time
        last_updated = component_statuses.order_by("-last_checked").first().last_checked

        # Format component statuses
        components = []
        for status in component_statuses:
            components.append(
                {
                    "id": str(status.id),
                    "component": status.component,
                    "name": status.get_component_display(),
                    "status": status.status,
                    "status_name": status.get_status_display(),
                    "description": status.description,
                    "last_checked": status.last_checked.isoformat(),
                }
            )

        # Check for active maintenance
        now = timezone.now()
        active_maintenance = MaintenanceSchedule.objects.filter(
            status="in_progress", start_time__lte=now, end_time__gt=now
        ).first()

        maintenance_info = None
        if active_maintenance:
            maintenance_info = {
                "id": str(active_maintenance.id),
                "title": active_maintenance.title,
                "start_time": active_maintenance.start_time.isoformat(),
                "end_time": active_maintenance.end_time.isoformat(),
                "affected_components": active_maintenance.affected_components,
            }

        return {
            "status": overall_status,
            "status_name": dict(PLATFORM_STATUS_CHOICES)[overall_status],
            "message": message,
            "last_updated": last_updated.isoformat(),
            "components": components,
            "active_maintenance": maintenance_info,
        }

    @staticmethod
    def refresh_status():
        """
        Trigger a manual refresh of component status checks.
        """
        # This would typically call the async task
        from ..tasks import update_platform_status

        update_platform_status.delay()

    @staticmethod
    def get_basic_health_check():
        """
        Perform a basic health check, suitable for external monitoring.

        Returns:
            dict: Basic health status
        """
        health_data = {
            "status": "healthy",
            "timestamp": timezone.now().isoformat(),
            "database": "connected",
            "checks": {},
        }

        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except OperationalError:
            health_data["status"] = "unhealthy"
            health_data["database"] = "disconnected"

        # Check system resources
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            health_data["checks"]["cpu"] = {
                "usage_percent": cpu_usage,
                "status": "ok" if cpu_usage < 90 else "high",
            }

            # Memory usage
            memory = psutil.virtual_memory()
            health_data["checks"]["memory"] = {
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "usage_percent": memory.percent,
                "status": "ok" if memory.percent < 90 else "high",
            }

            # Disk usage
            disk = psutil.disk_usage("/")
            health_data["checks"]["disk"] = {
                "total_gb": disk.total / (1024 * 1024 * 1024),
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "usage_percent": disk.percent,
                "status": "ok" if disk.percent < 90 else "high",
            }
        except Exception as e:
            logger.warning(f"Error checking system resources: {str(e)}")
            health_data["checks"]["system_resources"] = {
                "status": "error",
                "message": "Unable to check system resources",
            }

        # Overall status is unhealthy if any check is not ok
        for check_name, check in health_data["checks"].items():
            if check.get("status") != "ok":
                health_data["status"] = "degraded"

        return health_data

    @staticmethod
    def cancel_maintenance(maintenance, user):
        """
        Cancel a scheduled maintenance.

        Args:
            maintenance: The maintenance to cancel
            user: User cancelling the maintenance

        Returns:
            MaintenanceSchedule: The updated maintenance
        """
        maintenance.status = MAINTENANCE_CANCELLED
        maintenance.save()

        # Add a note about who cancelled it
        if not maintenance.description.endswith("(CANCELLED)"):
            maintenance.description += f"\n\nCANCELLED by {user.phone_number} at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            maintenance.save()

        # Create admin notification
        from .admin_service import AdminService

        AdminService.create_notification(
            title=f"Maintenance '{maintenance.title}' cancelled",
            message=f"The scheduled maintenance '{maintenance.title}' has been cancelled by {user.phone_number}.",
            level="info",
            data={"maintenance_id": str(maintenance.id)},
        )

        return maintenance

    @staticmethod
    def get_system_metrics():
        """
        Get detailed system performance metrics.

        Returns:
            dict: System metrics
        """
        metrics = {
            "timestamp": timezone.now().isoformat(),
            "system": {},
            "application": {},
            "database": {},
        }

        # System metrics
        try:
            # CPU
            metrics["system"]["cpu"] = {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(),
                "per_cpu": psutil.cpu_percent(interval=0.1, percpu=True),
            }

            # Memory
            memory = psutil.virtual_memory()
            metrics["system"]["memory"] = {
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "used_mb": memory.used / (1024 * 1024),
                "percent": memory.percent,
            }

            # Disk
            disk = psutil.disk_usage("/")
            metrics["system"]["disk"] = {
                "total_gb": disk.total / (1024 * 1024 * 1024),
                "used_gb": disk.used / (1024 * 1024 * 1024),
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "percent": disk.percent,
            }

            # Network
            net_io_start = psutil.net_io_counters()
            time.sleep(0.1)  # Brief sleep to measure rate
            net_io_end = psutil.net_io_counters()

            metrics["system"]["network"] = {
                "bytes_sent": net_io_end.bytes_sent,
                "bytes_recv": net_io_end.bytes_recv,
                "send_rate_kbps": (net_io_end.bytes_sent - net_io_start.bytes_sent)
                * 10
                / 1024,  # KB/s
                "recv_rate_kbps": (net_io_end.bytes_recv - net_io_start.bytes_recv)
                * 10
                / 1024,  # KB/s
            }
        except Exception as e:
            logger.warning(f"Error collecting system metrics: {str(e)}")
            metrics["system"]["error"] = str(e)

        # Application metrics (these would be populated with actual app metrics)
        metrics["application"] = {
            "requests_per_minute": 0,  # Placeholder
            "average_response_time_ms": 0,  # Placeholder
            "error_rate": 0,  # Placeholder
        }

        # Database metrics
        try:
            with connection.cursor() as cursor:
                # Measure query execution time
                start_time = time.time()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                query_time = (time.time() - start_time) * 1000  # ms

                metrics["database"]["query_time_ms"] = query_time

                # Get connection count (PostgreSQL)
                if connection.vendor == "postgresql":
                    cursor.execute(
                        """
                        SELECT count(*) FROM pg_stat_activity 
                        WHERE datname = current_database()
                    """
                    )
                    connections = cursor.fetchone()[0]
                    metrics["database"]["active_connections"] = connections
        except Exception as e:
            logger.warning(f"Error collecting database metrics: {str(e)}")
            metrics["database"]["error"] = str(e)

        return metrics
