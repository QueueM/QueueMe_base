import logging

from django.db import transaction
from django.utils import timezone

from apps.authapp.models import User
from apps.chatapp.models import Conversation, Message, Presence, TypingStatus
from apps.employeeapp.models import Employee
from apps.shopapp.models import Shop
from core.storage.s3_storage import S3Storage

logger = logging.getLogger("chatapp.services")


class ChatService:
    """Service for managing chat conversations and messages"""

    @staticmethod
    def get_or_create_conversation(customer_id, shop_id):
        """Get or create conversation between customer and shop"""
        customer = User.objects.get(id=customer_id)
        shop = Shop.objects.get(id=shop_id)

        conversation, created = Conversation.objects.get_or_create(customer=customer, shop=shop)

        # If new conversation, initialize presence records
        if created:
            # Create customer presence
            Presence.objects.create(user=customer, conversation=conversation, is_online=False)

            # Create presence records for shop employees with chat access
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            employees = Employee.objects.filter(shop=shop)

            for employee in employees:
                if PermissionResolver.has_permission(employee.user, "chat", "view"):
                    Presence.objects.create(
                        user=employee.user, conversation=conversation, is_online=False
                    )

        return conversation, created

    @staticmethod
    @transaction.atomic
    def send_message(
        conversation_id,
        sender_id,
        content,
        message_type="text",
        media_file=None,
        media_url=None,
        employee_id=None,
    ):
        """Send a message in a conversation"""
        conversation = Conversation.objects.get(id=conversation_id)
        sender = User.objects.get(id=sender_id)

        employee = None
        if employee_id:
            try:
                employee = Employee.objects.get(id=employee_id)
            except Employee.DoesNotExist:
                # Try to find employee by user ID
                try:
                    employee = Employee.objects.get(user_id=sender_id)
                except Employee.DoesNotExist:
                    pass
        elif sender.user_type != "customer":
            # If sender is not customer, try to get their employee record
            try:
                employee = Employee.objects.get(user=sender)
            except Employee.DoesNotExist:
                pass

        # Handle media if provided
        if media_file and message_type in ["image", "video"] and not media_url:
            # Upload to S3
            s3_storage = S3Storage()
            media_url = s3_storage.upload_file(
                media_file, f"chat/{conversation_id}/{message_type}s/"
            )

        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            employee=employee,
            content=content,
            message_type=message_type,
            media_url=media_url,
        )

        # Update conversation timestamp
        conversation.updated_at = timezone.now()
        conversation.save()

        # Update typing status (set to False after sending message)
        typing_status, _ = TypingStatus.objects.get_or_create(
            user=sender, conversation=conversation, defaults={"is_typing": False}
        )
        typing_status.is_typing = False
        typing_status.save()

        # Return the created message
        return message

    @staticmethod
    def mark_messages_as_read(conversation_id, user_id):
        """Mark all messages in conversation as read for a user"""
        conversation = Conversation.objects.get(id=conversation_id)
        user = User.objects.get(id=user_id)

        # Mark messages from other party as read
        if user.user_type == "customer":
            # Mark shop messages as read
            unread_messages = Message.objects.filter(
                conversation=conversation, is_read=False
            ).exclude(sender=user)
        else:
            # Mark customer messages as read
            unread_messages = Message.objects.filter(
                conversation=conversation, is_read=False, sender=conversation.customer
            )

        now = timezone.now()

        # Update all unread messages
        count = unread_messages.count()
        unread_messages.update(is_read=True, read_at=now)

        return count

    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread messages for a user"""
        user = User.objects.get(id=user_id)

        if user.user_type == "customer":
            # For customers, count unread messages in their conversations
            return (
                Message.objects.filter(conversation__customer=user, is_read=False)
                .exclude(sender=user)
                .count()
            )
        else:
            # For employees, count unread messages in their shop conversations
            employee = Employee.objects.filter(user=user).first()

            if not employee:
                return 0

            return Message.objects.filter(
                conversation__shop=employee.shop,
                is_read=False,
                sender__user_type="customer",  # Only count messages from customers
            ).count()

    @staticmethod
    def has_chat_permission(user_id):
        """Check if user has permission to access chat"""
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        # Get user
        user = User.objects.get(id=user_id)

        # Customers always have permission to chat
        if user.user_type == "customer":
            return True

        # For employees, check chat permission
        return PermissionResolver.has_permission(user, "chat", "view")

    @staticmethod
    def get_employee_conversations(employee_id):
        """Get all conversations for an employee's shop"""
        employee = Employee.objects.get(id=employee_id)

        # Check permission
        if not ChatService.has_chat_permission(employee.user.id):
            return Conversation.objects.none()

        # Get conversations for shop
        return Conversation.objects.filter(shop=employee.shop, is_active=True)

    @staticmethod
    def get_customer_conversations(customer_id):
        """Get all conversations for a customer"""
        customer = User.objects.get(id=customer_id)

        # Get conversations for customer
        return Conversation.objects.filter(customer=customer, is_active=True)

    @staticmethod
    @transaction.atomic
    def archive_conversation(conversation_id):
        """Archive a conversation (mark as inactive)"""
        conversation = Conversation.objects.get(id=conversation_id)
        conversation.is_active = False
        conversation.save()
        return conversation
