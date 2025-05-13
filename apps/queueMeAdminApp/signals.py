from django.db.models.signals import post_save
from django.dispatch import receiver

from .constants import AUDIT_ACTION_UPDATE, NOTIFICATION_LEVEL_INFO, NOTIFICATION_LEVEL_WARNING
from .models import (
    MaintenanceSchedule,
    PlatformStatus,
    SupportMessage,
    SupportTicket,
    VerificationRequest,
)
from .services.admin_service import AdminService


@receiver(post_save, sender=VerificationRequest)
def handle_verification_request_save(sender, instance, created, **kwargs):
    """Signal handler for verification request saves"""
    if created:
        # Create a notification for new verification requests
        AdminService.create_notification(
            title=f"New verification request for {instance.shop.name}",
            message=f"A new verification request has been submitted for {instance.shop.name}.",
            level=NOTIFICATION_LEVEL_INFO,
            data={
                "verification_id": str(instance.id),
                "shop_id": str(instance.shop.id),
                "shop_name": instance.shop.name,
            },
        )


@receiver(post_save, sender=SupportTicket)
def handle_support_ticket_save(sender, instance, created, **kwargs):
    """Signal handler for support ticket saves"""
    if created:
        # Create a notification for new support tickets
        AdminService.create_notification(
            title=f"New support ticket: {instance.reference_number}",
            message=f"A new support ticket has been created: {instance.subject}",
            level=(
                NOTIFICATION_LEVEL_INFO
                if instance.priority not in ["high", "urgent"]
                else NOTIFICATION_LEVEL_WARNING
            ),
            data={
                "ticket_id": str(instance.id),
                "reference_number": instance.reference_number,
                "category": instance.category,
                "priority": instance.priority,
            },
        )


@receiver(post_save, sender=SupportMessage)
def handle_support_message_save(sender, instance, created, **kwargs):
    """Signal handler for support message saves"""
    if created and not instance.is_from_admin:
        # Create a notification for new customer messages
        ticket = instance.ticket

        AdminService.create_notification(
            title=f"New message in ticket {ticket.reference_number}",
            message=f"Customer has replied to ticket: {ticket.subject}",
            level=NOTIFICATION_LEVEL_INFO,
            data={
                "ticket_id": str(ticket.id),
                "reference_number": ticket.reference_number,
                "message_id": str(instance.id),
            },
        )


@receiver(post_save, sender=PlatformStatus)
def handle_platform_status_save(sender, instance, created, **kwargs):
    """Signal handler for platform status saves"""
    if not created and "status" in kwargs.get("update_fields", ["status"]):
        # Log platform status changes in audit log
        prev_instance = sender.objects.get(pk=instance.pk)
        if prev_instance.status != instance.status:
            AdminService.log_audit(
                None,  # System audit - no specific user
                AUDIT_ACTION_UPDATE,
                "PlatformStatus",
                str(instance.id),
                {
                    "component": instance.component,
                    "old_status": prev_instance.status,
                    "new_status": instance.status,
                },
            )


@receiver(post_save, sender=MaintenanceSchedule)
def handle_maintenance_save(sender, instance, created, **kwargs):
    """Signal handler for maintenance schedule saves"""
    if created:
        # Create a notification for new maintenance schedule
        AdminService.create_notification(
            title=f"New maintenance scheduled: {instance.title}",
            message=f"A new maintenance event has been scheduled from {instance.start_time.strftime('%Y-%m-%d %H:%M')} to {instance.end_time.strftime('%Y-%m-%d %H:%M')}",
            level=NOTIFICATION_LEVEL_INFO,
            data={
                "maintenance_id": str(instance.id),
                "affected_components": instance.affected_components,
            },
        )
    elif "status" in kwargs.get("update_fields", ["status"]):
        # Status has changed, create notification
        AdminService.create_notification(
            title=f"Maintenance status updated: {instance.title}",
            message=f"The maintenance status has been updated to: {instance.get_status_display()}",
            level=NOTIFICATION_LEVEL_INFO,
            data={"maintenance_id": str(instance.id), "status": instance.status},
        )
