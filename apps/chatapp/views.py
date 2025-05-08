from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Conversation, Message, Presence
from .permissions import CanAccessChatPermission
from .serializers import (
    ConversationSerializer,
    CreateConversationSerializer,
    CreateMessageSerializer,
    MessageSerializer,
)
from .services.chat_service import ChatService
from .services.presence_service import PresenceService
from .services.response_suggester import ResponseSuggester


class ConversationViewSet(viewsets.ModelViewSet):
    """API endpoint for chat conversations"""

    serializer_class = ConversationSerializer
    permission_classes = [CanAccessChatPermission]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["updated_at"]
    ordering = ["-updated_at"]  # Most recent conversations first

    def get_queryset(self):
        """Filter conversations based on user role"""
        user = self.request.user

        if user.user_type == "customer":
            # Customers only see their own conversations
            return Conversation.objects.filter(customer=user, is_active=True)
        else:
            # Employees see conversations for their shop
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                return Conversation.objects.filter(shop=employee.shop, is_active=True)
            except Employee.DoesNotExist:
                return Conversation.objects.none()

    def get_serializer_class(self):
        """Use appropriate serializer based on action"""
        if self.action == "create":
            return CreateConversationSerializer
        return ConversationSerializer

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get messages for a conversation"""
        conversation = self.get_object()

        # Get pagination parameters
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        # Calculate offset for pagination
        offset = (page - 1) * page_size

        # Get messages with pagination (most recent first, then reverse for display)
        messages = conversation.messages.order_by("-created_at")[
            offset : offset + page_size
        ]
        messages = list(reversed(messages))  # Reverse for chronological order

        # Mark messages as read if user is not the sender
        user = request.user
        if user.user_type == "customer":
            # Mark shop messages as read
            unread_messages = messages.filter(is_read=False).exclude(sender=user)
        else:
            # Mark customer messages as read
            unread_messages = messages.filter(
                is_read=False, sender=conversation.customer
            )

        if unread_messages.exists():
            # Use chat service to mark messages as read
            ChatService.mark_messages_as_read(conversation.id, user.id)

        serializer = MessageSerializer(messages, many=True)

        # Get total count for pagination info
        total_count = conversation.messages.count()

        # Update user presence in conversation
        PresenceService.set_user_online(user.id, conversation.id)

        # Get suggested responses if employee
        suggestions = []
        if user.user_type != "customer" and messages:
            last_customer_message = (
                conversation.messages.filter(sender=conversation.customer)
                .order_by("-created_at")
                .first()
            )

            if last_customer_message:
                suggestions = ResponseSuggester.suggest_responses(
                    last_customer_message, conversation
                )

        return Response(
            {
                "results": serializer.data,
                "count": total_count,
                "suggestions": suggestions,
            }
        )

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message in a conversation"""
        conversation = self.get_object()

        # Add conversation to request data
        data = request.data.copy()
        data["conversation"] = conversation.id

        serializer = CreateMessageSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            # Use chat service to send message
            message = ChatService.send_message(
                conversation_id=conversation.id,
                sender_id=request.user.id,
                content=serializer.validated_data["content"],
                message_type=serializer.validated_data.get("message_type", "text"),
                media_url=serializer.validated_data.get("media_url"),
                employee_id=serializer.validated_data.get("employee_id"),
            )

            # Return serialized message
            return Response(
                MessageSerializer(message).data, status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark all messages in conversation as read"""
        conversation = self.get_object()
        user = request.user

        # Use chat service to mark messages as read
        count = ChatService.mark_messages_as_read(conversation.id, user.id)

        return Response({"marked_read": count})

    @action(detail=True, methods=["post"])
    def typing_status(self, request, pk=None):
        """Update typing status for user"""
        conversation = self.get_object()
        user = request.user

        # Get is_typing from request data
        is_typing = request.data.get("is_typing", False)

        # Use presence service to update typing status
        PresenceService.set_typing_status(user.id, conversation.id, is_typing)

        return Response({"status": "updated"})

    @action(detail=True, methods=["get"])
    def presence(self, request, pk=None):
        """Get presence information for all users in a conversation"""
        conversation = self.get_object()

        # Get presence records
        presence_records = Presence.objects.filter(conversation=conversation)

        # Format for response
        presence_data = {}
        for record in presence_records:
            presence_data[str(record.user.id)] = {
                "is_online": record.is_online,
                "last_seen": record.last_seen.strftime("%I:%M %p - %d %b, %Y"),
            }

        return Response(presence_data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get total unread message count across all conversations"""
        user = request.user

        # Use chat service to get unread count
        count = ChatService.get_unread_count(user.id)

        return Response({"unread_count": count})


class MessageViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """API endpoint for chat messages (limited functionality)"""

    serializer_class = MessageSerializer
    permission_classes = [CanAccessChatPermission]

    def get_queryset(self):
        """Filter messages based on user role"""
        user = self.request.user

        if user.user_type == "customer":
            # Customers only see messages in their conversations
            return Message.objects.filter(conversation__customer=user)
        else:
            # Employees see messages for their shop
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                return Message.objects.filter(conversation__shop=employee.shop)
            except Employee.DoesNotExist:
                return Message.objects.none()
