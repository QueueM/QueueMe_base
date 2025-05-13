from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notificationsapp.services.notification_service import NotificationService

from .models import Message


@receiver(post_save, sender=Message)
def update_conversation_timestamp(sender, instance, created, **kwargs):
    """Update conversation's updated_at timestamp when new message is added"""
    if created:
        conversation = instance.conversation
        conversation.save()  # This will update the updated_at field


@receiver(post_save, sender=Message)
def send_message_notification(sender, instance, created, **kwargs):
    """Send notification to message recipient"""
    if created:
        conversation = instance.conversation
        # Determine recipient (opposite party of sender)
        if instance.sender == conversation.customer:
            # Message from customer to shop - notify shop employees
            from apps.employeeapp.models import Employee
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            # Get employees with chat permission for this shop
            employees = Employee.objects.filter(shop=conversation.shop)
            for employee in employees:
                if PermissionResolver.has_permission(employee.user, "chat", "view"):
                    # Don't notify the sender if it's an employee
                    if employee.user != instance.sender:
                        # Send notification to employee
                        NotificationService.send_notification(
                            user_id=employee.user.id,
                            notification_type="new_message",
                            data={
                                "conversation_id": str(conversation.id),
                                "sender_name": conversation.customer.phone_number,
                                "message_preview": (
                                    instance.content[:50]
                                    if instance.message_type == "text"
                                    else f"New {instance.message_type}"
                                ),
                                "shop_name": conversation.shop.name,
                            },
                            channels=["push", "in_app"],
                        )
        else:
            # Message from shop to customer - notify customer
            NotificationService.send_notification(
                user_id=conversation.customer.id,
                notification_type="new_message",
                data={
                    "conversation_id": str(conversation.id),
                    "shop_name": conversation.shop.name,
                    "message_preview": (
                        instance.content[:50]
                        if instance.message_type == "text"
                        else f"New {instance.message_type}"
                    ),
                    "employee_name": (
                        instance.employee.first_name if instance.employee else "Shop"
                    ),
                },
                channels=["push", "in_app"],
            )
