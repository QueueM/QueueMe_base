import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.authapp.services.token_service import TokenService

from .models import Conversation, Employee, User
from .services.chat_service import ChatService
from .services.presence_service import PresenceService

logger = logging.getLogger("chatapp.consumers")


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""

    async def connect(self):
        """Handle WebSocket connection"""
        # Get token from query string
        query_string = self.scope["query_string"].decode()
        query_params = dict(x.split("=") for x in query_string.split("&"))
        token = query_params.get("token", "")

        # Verify token and get user
        user = await database_sync_to_async(TokenService.get_user_from_token)(token)

        if not user:
            # Reject connection if token is invalid
            logger.warning("WebSocket connection rejected: Invalid token")
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
            logger.warning(
                f"WebSocket connection rejected: User {self.user_id} has no access to conversation {self.conversation_id}"
            )
            await self.close(code=4003)
            return

        # Join conversation group
        await self.channel_layer.group_add(self.conversation_group_name, self.channel_name)

        # Mark user as online
        await database_sync_to_async(PresenceService.set_user_online)(
            self.user_id, self.conversation_id
        )

        # Broadcast presence update
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {"type": "presence_update", "user_id": self.user_id, "status": "online"},
        )

        await self.accept()

        # Mark messages as read
        await database_sync_to_async(ChatService.mark_messages_as_read)(
            self.conversation_id, self.user_id
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Mark user as offline
        if hasattr(self, "user_id") and hasattr(self, "conversation_id"):
            await database_sync_to_async(PresenceService.set_user_offline)(
                self.user_id, self.conversation_id
            )

            # Broadcast presence update
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "presence_update",
                    "user_id": self.user_id,
                    "status": "offline",
                },
            )

            # Leave conversation group
            await self.channel_layer.group_discard(self.conversation_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "text")

            if message_type == "message":
                # Handle text message
                content = data.get("content", "")
                message_type = data.get("message_type", "text")
                media_url = data.get("media_url")
                employee_id = data.get("employee_id")

                # Save message to database
                message = await database_sync_to_async(ChatService.send_message)(
                    self.conversation_id,
                    self.user_id,
                    content,
                    message_type,
                    media_url,
                    employee_id,
                )

                # Get user type for response
                # unused_unused_user = await database_sync_to_async(self.get_user)()
                conversation = await database_sync_to_async(self.get_conversation)()

                # Format created_at for response
                created_at = message.created_at.strftime("%I:%M %p - %d %b, %Y")

                # Get employee details if applicable
                employee_details = None
                if message.employee:
                    employee_details = await database_sync_to_async(self.get_employee_details)(
                        message.employee
                    )

                # Broadcast message to conversation group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "chat_message",
                        "message": {
                            "id": str(message.id),
                            "sender_id": str(message.sender.id),
                            "sender_type": (
                                "customer" if message.sender == conversation.customer else "shop"
                            ),
                            "content": message.content,
                            "message_type": message.message_type,
                            "media_url": message.media_url,
                            "created_at": created_at,
                            "is_read": message.is_read,
                            "employee": (str(message.employee.id) if message.employee else None),
                            "employee_details": employee_details,
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

                # Update typing status
                await database_sync_to_async(PresenceService.set_typing_status)(
                    self.user_id, self.conversation_id, is_typing
                )

                # Broadcast typing status to conversation group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "typing_indicator",
                        "user_id": self.user_id,
                        "is_typing": is_typing,
                    },
                )
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")

    async def chat_message(self, event):
        """Send message to WebSocket"""
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))

    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({"type": "read_receipt", "user_id": event["user_id"]}))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
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
        """Send presence update to WebSocket"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event["user_id"],
                    "status": event["status"],
                }
            )
        )

    def check_conversation_access(self):
        """Check if user has access to this conversation"""
        try:
            user = User.objects.get(id=self.user_id)
            conversation = Conversation.objects.get(id=self.conversation_id)

            if user.user_type == "customer":
                # Customer can only access their own conversations
                return conversation.customer_id == self.user_id
            else:
                # Employee can access conversations of their shop
                employee = Employee.objects.filter(user_id=self.user_id).first()

                if not employee:
                    return False

                # Check if employee's shop matches conversation's shop
                if employee.shop_id != conversation.shop_id:
                    return False

                # Check if employee has chat permission
                from apps.rolesapp.services.permission_resolver import PermissionResolver

                return PermissionResolver.has_permission(user, "chat", "view")
        except Exception as e:
            logger.error(f"Error checking conversation access: {str(e)}")
            return False

    def get_user(self):
        """Get user object"""
        return User.objects.get(id=self.user_id)

    def get_conversation(self):
        """Get conversation object"""
        return Conversation.objects.get(id=self.conversation_id)

    def get_employee_details(self, employee):
        """Get employee details for response"""
        try:
            # Get role information
            from apps.rolesapp.models import UserRole

            user_role = UserRole.objects.filter(user=employee.user).first()
            role_name = user_role.role.name if user_role else None

            return {
                "id": str(employee.id),
                "user_id": str(employee.user.id),
                "phone_number": employee.user.phone_number,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "role": role_name,
                "avatar": employee.avatar.url if employee.avatar else None,
                "position": employee.position,
            }
        except Exception as e:
            logger.error(f"Error getting employee details: {str(e)}")
            return None
