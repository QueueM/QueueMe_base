"""
WebSocket consumer for real-time notifications.

This consumer provides real-time notifications to users for various events.
"""

import json
import logging
from typing import Any, Dict, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.notificationsapp.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: Optional[str] = None
        self.notification_group_name: Optional[str] = None

    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get token from query string
            query_string = self.scope["query_string"].decode()
            query_params = dict(
                x.split("=") for x in query_string.split("&") if "=" in x
            )
            token = query_params.get("token", "")

            if not token:
                logger.warning("Notification connection rejected: No token provided")
                await self.close(code=4001)
                return

            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if not user:
                logger.warning("Notification connection rejected: Invalid token")
                await self.close(code=4001)
                return

            if not user.is_active:
                logger.warning(
                    f"Notification connection rejected: User {user.id} is inactive"
                )
                await self.close(code=4002)
                return

            self.user_id = str(user.id)

            # Verify user_id from token matches user_id from URL
            url_user_id = self.scope["url_route"]["kwargs"]["user_id"]
            if str(user.id) != url_user_id:
                logger.warning(
                    f"Notification connection rejected: User ID mismatch. Token: {user.id}, URL: {url_user_id}"
                )
                await self.close(code=4003)
                return

            # Set up notification group for this user
            self.notification_group_name = f"notifications_{self.user_id}"

            # Join notification group
            await self.channel_layer.group_add(
                self.notification_group_name, self.channel_name
            )

            # Accept connection
            await self.accept()

            # Send unread notification count on connect
            await self.send_unread_count()

            logger.info(f"Notification connection established for user {self.user_id}")

        except Exception as e:
            logger.error(f"Error in notification connection: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if self.notification_group_name:
                await self.channel_layer.group_discard(
                    self.notification_group_name, self.channel_name
                )
            logger.info(f"Notification connection closed for user {self.user_id}")
        except Exception as e:
            logger.error(f"Error in notification disconnection: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "mark_read":
                await self.handle_mark_read(data)
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            else:
                logger.warning(f"Received unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.warning("Received invalid JSON data")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    async def handle_mark_read(self, data: Dict[str, Any]):
        """Handle mark notification as read request."""
        try:
            notification_id = data.get("notification_id")
            if not notification_id:
                return

            # Mark notification as read
            success = await database_sync_to_async(
                NotificationService.mark_notification_read
            )(notification_id, self.user_id)

            if success:
                # Send updated unread count
                await self.send_unread_count()

        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")

    async def notification_message(self, event):
        """Handle notification message events."""
        try:
            await self.send(
                text_data=json.dumps(
                    {"type": "notification", "data": event["data"]},
                    cls=DjangoJSONEncoder,
                )
            )
        except Exception as e:
            logger.error(f"Error sending notification message: {str(e)}")

    async def send_unread_count(self):
        """Send unread notification count to the client."""
        try:
            count = await database_sync_to_async(NotificationService.get_unread_count)(
                self.user_id
            )

            await self.send(
                text_data=json.dumps({"type": "unread_count", "count": count})
            )
        except Exception as e:
            logger.error(f"Error sending unread count: {str(e)}")
