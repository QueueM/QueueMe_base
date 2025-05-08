"""
WebSocket consumer for live chat.

This consumer provides real-time chat functionality between customers and shop employees.
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.chatapp.models import Conversation
from apps.chatapp.services.chat_service import ChatService
from apps.chatapp.services.presence_service import PresenceService


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality."""

    async def connect(self):
        """Handle WebSocket connection."""
        # Get token from query string
        query_string = self.scope["query_string"].decode()
        query_params = dict(x.split("=") for x in query_string.split("&") if "=" in x)
        token = query_params.get("token", "")

        # Verify token and get user
        user = await database_sync_to_async(TokenService.get_user_from_token)(token)

        if not user:
            # Reject connection if token is invalid
            await self.close(code=4001)
            return

        self.user_id = str(user.id)

        # Get conversation ID from URL
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation_group_name = f"chat_{self.conversation_id}"

        # Check if user has access to this conversation
        has_access = await database_sync_to_async(self.check_conversation_access)()

        if not has_access:
            # Reject connection if user doesn't have access
            await self.close(code=4003)
            return

        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name, self.channel_name
        )

        # Mark user as online
        await database_sync_to_async(PresenceService.set_user_online)(
            self.user_id, self.conversation_id
        )

        # Broadcast presence update
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {"type": "presence_update", "user_id": self.user_id, "status": "online"},
        )

        # Accept connection
        await self.accept()

        # Mark messages as read
        await database_sync_to_async(ChatService.mark_messages_as_read)(
            self.conversation_id, self.user_id
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Mark user as offline
        await database_sync_to_async(PresenceService.set_user_offline)(
            self.user_id, self.conversation_id
        )

        # Broadcast presence update
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {"type": "presence_update", "user_id": self.user_id, "status": "offline"},
        )

        # Leave conversation group
        await self.channel_layer.group_discard(
            self.conversation_group_name, self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages received from the WebSocket client."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "text")

            if message_type == "text":
                # Handle text message
                content = data.get("content", "")
                employee_id = data.get("employee_id")

                # Save message to database
                message = await database_sync_to_async(ChatService.send_message)(
                    self.conversation_id,
                    self.user_id,
                    content,
                    "text",
                    None,
                    employee_id,
                )

                # Prepare employee data if employee is set
                employee_data = None
                if message.employee:
                    employee_data = {
                        "id": str(message.employee.id),
                        "first_name": message.employee.first_name,
                        "last_name": message.employee.last_name,
                        "position": message.employee.position,
                    }

                # Broadcast message to conversation group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "chat_message",
                        "message": {
                            "id": str(message.id),
                            "sender_id": str(message.sender.id),
                            "content": message.content,
                            "message_type": message.message_type,
                            "created_at": message.created_at.isoformat(),
                            "is_read": message.is_read,
                            "employee": employee_data,
                        },
                    },
                )
            elif message_type == "read_receipt":
                # Handle read receipt
                await database_sync_to_async(ChatService.mark_messages_as_read)(
                    self.conversation_id, self.user_id
                )

                # Broadcast read receipt to conversation group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {"type": "read_receipt", "user_id": self.user_id},
                )
            elif message_type == "typing":
                # Handle typing indicator
                is_typing = data.get("is_typing", False)

                # Broadcast typing status to conversation group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "typing_indicator",
                        "user_id": self.user_id,
                        "is_typing": is_typing,
                    },
                )
            elif message_type == "heartbeat":
                # Respond to heartbeat to keep connection alive
                await self.send(text_data=json.dumps({"type": "heartbeat_response"}))
        except json.JSONDecodeError:
            # Invalid JSON, ignore
            pass

    async def chat_message(self, event):
        """Handle chat message events."""
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "message", "message": event["message"]}, cls=DjangoJSONEncoder
            )
        )

    async def read_receipt(self, event):
        """Handle read receipt events."""
        # Send read receipt to WebSocket
        await self.send(
            text_data=json.dumps({"type": "read_receipt", "user_id": event["user_id"]})
        )

    async def typing_indicator(self, event):
        """Handle typing indicator events."""
        # Send typing indicator to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def presence_update(self, event):
        """Handle presence update events."""
        # Send presence update to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event["user_id"],
                    "status": event["status"],
                }
            )
        )

    async def media_message(self, event):
        """Handle media message events."""
        # Send media message to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "media", "message": event["message"]}, cls=DjangoJSONEncoder
            )
        )

    def check_conversation_access(self):
        """Check if user has access to this conversation."""
        from apps.authapp.models import User
        from apps.employeeapp.models import Employee

        user = User.objects.get(id=self.user_id)

        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
        except Conversation.DoesNotExist:
            return False

        if user.user_type == "customer":
            # Customer can only access their own conversations
            return conversation.customer_id == self.user_id
        else:
            # Employee can access conversations of their shop
            try:
                employee = Employee.objects.filter(user_id=self.user_id).first()

                if not employee:
                    return False

                # Check if employee's shop matches conversation's shop
                if employee.shop_id != conversation.shop_id:
                    return False

                # Check if employee has chat permission
                return ChatService.has_chat_permission(self.user_id)
            except Exception:
                return False
