import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

from .constants import (
    COMPONENT_API,
    COMPONENT_BOOKING,
    COMPONENT_DATABASE,
    COMPONENT_NOTIFICATION,
    COMPONENT_PAYMENT,
    COMPONENT_QUEUE,
    MAINTENANCE_COMPLETED,
    MAINTENANCE_IN_PROGRESS,
    MAINTENANCE_SCHEDULED,
    NOTIFICATION_LEVEL_ERROR,
    NOTIFICATION_LEVEL_INFO,
    NOTIFICATION_LEVEL_WARNING,
    PLATFORM_STATUS_DEGRADED,
    PLATFORM_STATUS_OPERATIONAL,
)
from .models import (
    AdminNotification,
    AuditLog,
    MaintenanceSchedule,
    PlatformStatus,
    SystemSetting,
    VerificationRequest,
)

logger = logging.getLogger(__name__)


@shared_task
def check_pending_verifications():
    """
    Check for verification requests that have been pending for too long
    and notify admins.
    """
    # Get the threshold from settings or use default (3 days)
    try:
        setting = SystemSetting.objects.get(key="VERIFICATION_REMINDER_DAYS")
        threshold_days = int(setting.value)
    except (SystemSetting.DoesNotExist, ValueError):
        threshold_days = 3

    threshold_date = timezone.now() - timedelta(days=threshold_days)

    # Find pending verification requests older than the threshold
    pending_verifications = VerificationRequest.objects.filter(
        status="pending", submitted_at__lt=threshold_date
    )

    if pending_verifications.exists():
        # Create admin notification
        count = pending_verifications.count()
        AdminNotification.objects.create(
            title=f"{count} verification request(s) pending for more than {threshold_days} days",
            message=f"There are {count} shop verification requests that have been pending for more than {threshold_days} days. Please review them.",
            level=NOTIFICATION_LEVEL_WARNING,
            data={
                "count": count,
                "verification_ids": [str(v.id) for v in pending_verifications],
            },
        )

        logger.info(f"Created notification for {count} pending verification requests")


@shared_task
def update_platform_status():
    """
    Check system components' health and update platform status
    """
    components = [
        COMPONENT_API,
        COMPONENT_DATABASE,
        COMPONENT_QUEUE,
        COMPONENT_BOOKING,
        COMPONENT_PAYMENT,
        COMPONENT_NOTIFICATION,
    ]

    for component in components:
        try:
            # Here we would implement real health checks for each component
            # For now, we'll simulate with dummy checks

            # Get current status
            status_obj, created = PlatformStatus.objects.get_or_create(
                component=component, defaults={"status": PLATFORM_STATUS_OPERATIONAL}
            )

            # Perform component-specific health check
            status, metrics = _check_component_health(component)

            # Update status if changed
            if status != status_obj.status:
                old_status = status_obj.status
                status_obj.status = status
                status_obj.save()

                # Create notification if degraded
                if status != PLATFORM_STATUS_OPERATIONAL:
                    level = (
                        NOTIFICATION_LEVEL_WARNING
                        if status == PLATFORM_STATUS_DEGRADED
                        else NOTIFICATION_LEVEL_ERROR
                    )
                    AdminNotification.objects.create(
                        title=f"{status_obj.get_component_display()} status changed to {status_obj.get_status_display()}",
                        message=f"The {status_obj.get_component_display()} component status has changed from {old_status} to {status}.",
                        level=level,
                        data={
                            "component": component,
                            "old_status": old_status,
                            "new_status": status,
                            "metrics": metrics,
                        },
                    )

            # Always update metrics
            status_obj.metrics = metrics
            status_obj.save()

        except Exception as e:
            logger.error(f"Error checking status for component {component}: {str(e)}")

            # Create error notification
            AdminNotification.objects.create(
                title=f"Error checking {component} status",
                message=f"An error occurred while checking the status of {component}: {str(e)}",
                level=NOTIFICATION_LEVEL_ERROR,
                data={"component": component, "error": str(e)},
            )


def _check_component_health(component):
    """
    Perform health check for a specific component
    Returns (status, metrics)
    """
    # This would be implemented with real health checks
    # For now we'll return dummy data

    if component == COMPONENT_API:
        # Check API response times, error rates, etc.
        return PLATFORM_STATUS_OPERATIONAL, {
            "response_time_ms": 120,
            "error_rate": 0.01,
            "requests_per_minute": 350,
        }

    elif component == COMPONENT_DATABASE:
        # Check database connections, query times, etc.
        return PLATFORM_STATUS_OPERATIONAL, {
            "connections": 15,
            "avg_query_time_ms": 5.2,
            "free_space_gb": 452,
        }

    elif component == COMPONENT_QUEUE:
        # Check queue system performance
        return PLATFORM_STATUS_OPERATIONAL, {
            "active_queues": 28,
            "avg_wait_time_min": 5.4,
            "total_waiting_customers": 43,
        }

    elif component == COMPONENT_BOOKING:
        # Check booking system performance
        return PLATFORM_STATUS_OPERATIONAL, {
            "bookings_today": 156,
            "avg_booking_time_sec": 3.2,
            "failure_rate": 0.005,
        }

    elif component == COMPONENT_PAYMENT:
        # Check payment system
        return PLATFORM_STATUS_OPERATIONAL, {
            "transactions_today": 89,
            "success_rate": 0.995,
            "avg_processing_time_sec": 2.1,
        }

    elif component == COMPONENT_NOTIFICATION:
        # Check notification delivery
        return PLATFORM_STATUS_OPERATIONAL, {
            "sms_delivery_rate": 0.99,
            "push_delivery_rate": 0.97,
            "avg_delivery_time_sec": 1.2,
        }

    # Default for unknown components
    return PLATFORM_STATUS_OPERATIONAL, {}


@shared_task
def manage_maintenance_schedules():
    """
    Manage scheduled maintenance events:
    - Transition scheduled -> in progress when start time is reached
    - Transition in progress -> completed when end time is reached
    """
    now = timezone.now()

    # Find scheduled maintenance that should now be in progress
    scheduled = MaintenanceSchedule.objects.filter(
        status=MAINTENANCE_SCHEDULED, start_time__lte=now, end_time__gt=now
    )

    for maintenance in scheduled:
        maintenance.status = MAINTENANCE_IN_PROGRESS
        maintenance.save()

        # Create notification
        AdminNotification.objects.create(
            title=f"Maintenance '{maintenance.title}' is now in progress",
            message=f"The scheduled maintenance '{maintenance.title}' has started and is now in progress.",
            level=NOTIFICATION_LEVEL_INFO,
            data={
                "maintenance_id": str(maintenance.id),
                "end_time": maintenance.end_time.isoformat(),
            },
        )

    # Find in-progress maintenance that should now be completed
    in_progress = MaintenanceSchedule.objects.filter(
        status=MAINTENANCE_IN_PROGRESS, end_time__lte=now
    )

    for maintenance in in_progress:
        maintenance.status = MAINTENANCE_COMPLETED
        maintenance.save()

        # Create notification
        AdminNotification.objects.create(
            title=f"Maintenance '{maintenance.title}' is now completed",
            message=f"The maintenance '{maintenance.title}' has been completed.",
            level=NOTIFICATION_LEVEL_INFO,
            data={
                "maintenance_id": str(maintenance.id),
                "duration_minutes": int(
                    (maintenance.end_time - maintenance.start_time).total_seconds() / 60
                ),
            },
        )


@shared_task
def generate_system_summary_report():
    """
    Generate a daily summary report of system activity.
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    start_of_yesterday = timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    end_of_yesterday = timezone.datetime.combine(yesterday, timezone.datetime.max.time())

    # Get stats for the day
    new_shops = Shop.objects.filter(
        created_at__range=(start_of_yesterday, end_of_yesterday)
    ).count()
    verified_shops = VerificationRequest.objects.filter(
        verified_at__range=(start_of_yesterday, end_of_yesterday), status="approved"
    ).count()

    new_specialists = Specialist.objects.filter(
        created_at__range=(start_of_yesterday, end_of_yesterday)
    ).count()

    # Logging activity would also include bookings, queue tickets, etc.
    # This would require importing more models

    # Create admin notification with daily summary
    AdminNotification.objects.create(
        title=f"System activity summary for {yesterday.strftime('%Y-%m-%d')}",
        message=f"New shops: {new_shops}\nVerified shops: {verified_shops}\nNew specialists: {new_specialists}",
        level=NOTIFICATION_LEVEL_INFO,
        data={
            "date": yesterday.strftime("%Y-%m-%d"),
            "new_shops": new_shops,
            "verified_shops": verified_shops,
            "new_specialists": new_specialists,
            # Other stats would be added here
        },
    )

    logger.info(f"Generated system summary report for {yesterday}")


@shared_task
def cleanup_old_audit_logs():
    """
    Clean up old audit logs based on retention policy.
    """
    # Get retention period from settings or use default (90 days)
    try:
        setting = SystemSetting.objects.get(key="AUDIT_LOG_RETENTION_DAYS")
        retention_days = int(setting.value)
    except (SystemSetting.DoesNotExist, ValueError):
        retention_days = 90

    if retention_days <= 0:
        # No cleanup if retention is set to zero or negative
        return

    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Count logs to be deleted
    logs_to_delete = AuditLog.objects.filter(timestamp__lt=cutoff_date)
    count = logs_to_delete.count()

    if count > 0:
        # Delete old logs
        logs_to_delete.delete()
        logger.info(f"Deleted {count} audit logs older than {retention_days} days")
