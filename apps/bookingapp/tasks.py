# apps/bookingapp/tasks.py
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.bookingapp.services.reminder_service import ReminderService


@shared_task
def process_due_reminders():
    """Process all reminders that are due to be sent"""
    count = ReminderService.process_due_reminders()
    return f"Processed {count} reminders"


@shared_task
def check_no_shows():
    """Check for potential no-shows (customers who didn't show up)"""
    # Get appointments that started more than 30 minutes ago
    # and are still in scheduled/confirmed status
    threshold_time = timezone.now() - timedelta(minutes=30)

    potential_no_shows = Appointment.objects.filter(
        status__in=["scheduled", "confirmed"], start_time__lt=threshold_time
    )

    count = 0
    for appointment in potential_no_shows:
        # Mark as no-show
        appointment.mark_no_show()
        count += 1

        # Notify shop about no-show
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        NotificationService.send_no_show_alert(appointment)

    return f"Marked {count} appointments as no-show"


@shared_task
def send_upcoming_appointment_summary():
    """Send daily summary of upcoming appointments to shops"""
    # Get appointments for tomorrow
    tomorrow = timezone.now().date() + timedelta(days=1)

    # Group by shop
    from django.db.models import Count

    shop_summary = (
        Appointment.objects.filter(
            start_time__date=tomorrow, status__in=["scheduled", "confirmed"]
        )
        .values("shop")
        .annotate(appointment_count=Count("id"))
    )

    # Send summary to each shop
    count = 0
    for summary in shop_summary:
        shop_id = summary["shop"]
        # unused_unused_appointment_count = summary["appointment_count"]

        # Get shop's appointments for tomorrow
        shop_appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__date=tomorrow,
            status__in=["scheduled", "confirmed"],
        ).order_by("start_time")

        # Send notification to shop manager
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )
        from apps.shopapp.models import Shop

        shop = Shop.objects.get(id=shop_id)
        if shop.manager:
            NotificationService.send_appointment_summary(
                shop.manager, shop, shop_appointments, tomorrow
            )
            count += 1

    return f"Sent appointment summaries to {count} shops"
