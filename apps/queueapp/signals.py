from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import QueueTicket
from .services.queue_service import QueueService


@receiver(post_save, sender=QueueTicket)
def ticket_saved(sender, instance, created, **kwargs):
    """Signal fired when a queue ticket is saved"""
    # Skip if this is a new ticket (creation is handled in service)
    if created:
        return

    # Recalculate wait times for affected tickets
    QueueService.recalculate_wait_times(instance.queue_id)

    # Notify relevant channels about the update
    if instance.status in ["waiting", "called", "serving", "served", "cancelled"]:
        channel_layer = get_channel_layer()

        # Send update to queue group
        queue_group_name = f"queue_{instance.queue_id}"

        async_to_sync(channel_layer.group_send)(
            queue_group_name,
            {
                "type": "queue_update",
                "action": "update",
                "ticket": {
                    "id": str(instance.id),
                    "ticket_number": instance.ticket_number,
                    "status": instance.status,
                    "position": instance.position,
                    "estimated_wait_time": instance.estimated_wait_time,
                },
            },
        )


@receiver(post_delete, sender=QueueTicket)
def ticket_deleted(sender, instance, **kwargs):
    """Signal fired when a queue ticket is deleted"""
    # Recalculate wait times for remaining tickets
    QueueService.recalculate_wait_times(instance.queue_id)

    # Notify relevant channels about the deletion
    channel_layer = get_channel_layer()

    # Send update to queue group
    queue_group_name = f"queue_{instance.queue_id}"

    async_to_sync(channel_layer.group_send)(
        queue_group_name,
        {
            "type": "queue_update",
            "action": "delete",
            "ticket": {"id": str(instance.id), "ticket_number": instance.ticket_number},
        },
    )
