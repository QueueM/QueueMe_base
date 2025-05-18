import logging

from celery import shared_task
from django.utils import timezone

from apps.notificationsapp.services.notification_service import NotificationService

from .models import Queue, QueueTicket
from .services.queue_service import QueueService

logger = logging.getLogger(__name__)


@shared_task
def process_queue_notifications():
    """Process queue notifications for customers who are about to be called"""
    try:
        # Get active tickets in "waiting" status
        # unused_unused_now = timezone.now()
        waiting_tickets = QueueTicket.objects.filter(status="waiting").select_related(
            "queue", "customer"
        )

        for ticket in waiting_tickets:
            # If position is 1 or 2, send a notification that they'll be called soon
            if ticket.position <= 2:
                # Send notification
                NotificationService.send_notification(
                    user_id=ticket.customer.id,
                    notification_type="queue_status_update",
                    data={
                        "ticket_id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "shop_name": ticket.queue.shop.name,
                        "position": ticket.position,
                        "estimated_wait": ticket.estimated_wait_time,
                    },
                    channels=["push", "sms"],
                )

        return f"Processed {waiting_tickets.count()} queue notifications"
    except Exception as e:
        logger.error(f"Error processing queue notifications: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def cleanup_stale_queue_tickets():
    """Clean up tickets that have been in 'called' status for too long"""
    try:
        # Get tickets that have been in 'called' status for more than 15 minutes
        now = timezone.now()
        timeout_threshold = now - timezone.timedelta(minutes=15)

        stale_tickets = QueueTicket.objects.filter(
            status="called", called_time__lt=timeout_threshold
        )

        for ticket in stale_tickets:
            # Mark as skipped
            ticket.status = "skipped"
            ticket.save()

            # Send notification to customer
            NotificationService.send_notification(
                user_id=ticket.customer.id,
                notification_type="queue_cancelled",
                data={
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "shop_name": ticket.queue.shop.name,
                    "reason": "No show after being called",
                },
                channels=["push", "sms"],
            )

        return f"Cleaned up {stale_tickets.count()} stale queue tickets"
    except Exception as e:
        logger.error(f"Error cleaning up stale queue tickets: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def update_queue_wait_times():
    """Periodically update wait time estimates for all active queues"""
    try:
        # Get all active queues
        active_queues = Queue.objects.filter(status="open")

        for queue in active_queues:
            QueueService.recalculate_wait_times(queue.id)

        return f"Updated wait times for {active_queues.count()} queues"
    except Exception as e:
        logger.error(f"Error updating queue wait times: {str(e)}")
        return f"Error: {str(e)}"
