"""
WebSocket consumer for live chat.

This consumer provides real-time chat functionality between customers and shop employees.
"""

import json
import logging
from typing import Any, Dict, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.chatapp.models import Conversation, Message
from apps.chatapp.services.chat_service import ChatService
from apps.chatapp.services.presence_service import PresenceService

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self.conversation_group_name: Optional[str] = None
        self.conversation: Optional[Conversation] = None

    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get token from query string
            query_string = self.scope["query_string"].decode()
            query_params = dict(x.split("=") for x in query_string.split("&") if "=" in x)
            token = query_params.get("token", "")

            if not token:
                logger.warning("Chat connection rejected: No token provided")
                await self.close(code=4001)
                return

            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if not user:
                logger.warning("Chat connection rejected: Invalid token")
                await self.close(code=4001)
                return

            if not user.is_active:
                logger.warning(f"Chat connection rejected: User {user.id} is inactive")
                await self.close(code=4002)
                return

            self.user_id = str(user.id)

            # Get conversation ID from URL
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.conversation_group_name = f"chat_{self.conversation_id}"

            # Check if user has access to this conversation
            has_access = await database_sync_to_async(self.check_conversation_access)()

            if not has_access:
                logger.warning(
                    f"Chat connection rejected: User {self.user_id} has no access to conversation {self.conversation_id}"
                )
                await self.close(code=4003)
                return

            # Join conversation group
            await self.channel_layer.group_add(self.conversation_group_name, self.channel_name)

            # Accept connection
            await self.accept()

            # Update user presence
            await database_sync_to_async(PresenceService.update_presence)(
                self.user_id, self.conversation_id, True
            )

            # Send conversation history
            await self.send_conversation_history()

            logger.info(
                f"Chat connection established for user {self.user_id} to conversation {self.conversation_id}"
            )

        except Exception as e:
            logger.error(f"Error in chat connection: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if self.conversation_group_name:
                await self.channel_layer.group_discard(
                    self.conversation_group_name, self.channel_name
                )

            # Update user presence
            if self.user_id and self.conversation_id:
                await database_sync_to_async(PresenceService.update_presence)(
                    self.user_id, self.conversation_id, False
                )

            logger.info(
                f"Chat connection closed for user {self.user_id} to conversation {self.conversation_id}"
            )
        except Exception as e:
            logger.error(f"Error in chat disconnection: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "message":
                await self.handle_message(data)
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            elif message_type == "typing":
                await self.handle_typing(data)
            else:
                logger.warning(f"Received unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.warning("Received invalid JSON data")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    async def handle_message(self, data: Dict[str, Any]):
        """Handle incoming chat message."""
        try:
            message_text = data.get("message", "").strip()
            if not message_text:
                return

            # Validate message length
            if len(message_text) > 1000:  # Maximum message length
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": "Message too long. Maximum length is 1000 characters.",
                        }
                    )
                )
                return

            # Save message to database
            message = await database_sync_to_async(self.save_message)(message_text)

            if not message:
                return

            # Broadcast message to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": str(message.id),
                        "sender_id": str(message.sender_id),
                        "text": message.text,
                        "timestamp": message.created_at.isoformat(),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Failed to send message. Please try again.",
                    }
                )
            )

    async def handle_typing(self, data: Dict[str, Any]):
        """Handle typing indicator."""
        try:
            is_typing = data.get("is_typing", False)

            # Broadcast typing status to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "typing_status",
                    "user_id": self.user_id,
                    "is_typing": is_typing,
                },
            )

        except Exception as e:
            logger.error(f"Error handling typing status: {str(e)}")

    async def chat_message(self, event):
        """Handle chat message events."""
        try:
            await self.send(
                text_data=json.dumps(
                    {"type": "message", "data": event["message"]},
                    cls=DjangoJSONEncoder,
                )
            )
        except Exception as e:
            logger.error(f"Error sending chat message: {str(e)}")

    async def typing_status(self, event):
        """Handle typing status events."""
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing",
                        "user_id": event["user_id"],
                        "is_typing": event["is_typing"],
                    }
                )
            )
        except Exception as e:
            logger.error(f"Error sending typing status: {str(e)}")

    async def send_conversation_history(self):
        """Send conversation history to the client."""
        try:
            messages = await database_sync_to_async(self.get_conversation_messages)()
            await self.send(
                text_data=json.dumps(
                    {"type": "history", "messages": messages}, cls=DjangoJSONEncoder
                )
            )
        except Exception as e:
            logger.error(f"Error sending conversation history: {str(e)}")

    def check_conversation_access(self):
        """Check if user has access to this conversation."""
        try:
            self.conversation = Conversation.objects.get(id=self.conversation_id)
            return ChatService.check_user_conversation_access(self.user_id, self.conversation)
        except Conversation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking conversation access: {str(e)}")
            return False

    def save_message(self, text: str) -> Optional[Message]:
        """Save message to database."""
        try:
            return ChatService.create_message(
                conversation_id=self.conversation_id,
                sender_id=self.user_id,
                text=text,
            )
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None

    def get_conversation_messages(self):
        """Get conversation messages."""
        try:
            return ChatService.get_conversation_messages(
                conversation_id=self.conversation_id,
                limit=50,  # Limit to last 50 messages
            )
        except Exception as e:
            logger.error(f"Error getting conversation messages: {str(e)}")
            return []
