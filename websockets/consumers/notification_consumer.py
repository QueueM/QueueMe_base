import json
import logging
from typing import Any, Dict, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

from apps.notificationsapp.enums import NotificationType
from apps.notificationsapp.models import Notification
from core.cache.advanced_cache import AdvancedCache, cached
from websockets.consumers.socket_helpers import (
    SwiftCompatibleMessage,
    get_client_preferences,
    send_to_client,
)

logger = logging.getLogger(__name__)

# Initialize cache for consumer state
consumer_cache = AdvancedCache("websocket")
User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications with Swift client optimizations
    """

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user from scope
            self.user = self.scope.get("user")
            self.user_id = str(self.user.id) if self.user and self.user.is_authenticated else None

            if not self.user_id:
                await self.close(code=4003)  # Unauthorized
                return

            # Add to notification group for this user
            self.user_group_name = f"notifications_{self.user_id}"
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)

            # Accept the connection
            await self.accept()

            # Get client preferences for optimizations
            client_preferences = await get_client_preferences(self.user_id)
            self.is_ios = client_preferences.get("platform") == "ios"
            self.client_language = client_preferences.get("language", "ar")

            # Store client ID if provided in query string (used by Swift clients)
            self.client_id = None
            if "client_id" in self.scope.get("query_string", b"").decode("utf-8"):
                for param in self.scope["query_string"].decode("utf-8").split("&"):
                    if param.startswith("client_id="):
                        self.client_id = param.split("=")[1]
                        break

            # Send connection success message
            await send_to_client(
                self,
                "connection_established",
                {
                    "user_id": self.user_id,
                    "status": "connected",
                    "supports_compression": True,
                    "supports_binary": True,
                },
                client_id=self.client_id,
            )

            # Check for pending notifications immediately
            await self.send_pending_notifications()

            logger.info(f"WebSocket connected for user {self.user_id}")

        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}")
            await self.close(code=4500)  # Internal error

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Remove from notification group
            if hasattr(self, "user_group_name"):
                await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

            logger.info(f"WebSocket disconnected for user {getattr(self, 'user_id', 'unknown')}")

        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages from client"""
        try:
            if text_data:
                # Parse JSON message
                data = json.loads(text_data)
                message_type = data.get("type")

                # Handle message based on type
                if message_type == "ping":
                    # Respond to ping with pong
                    await send_to_client(
                        self,
                        "pong",
                        {"timestamp": data.get("timestamp")},
                        client_id=self.client_id or data.get("client_id"),
                    )

                elif message_type == "acknowledge_notification":
                    # Client acknowledging notification receipt
                    notification_id = data.get("notification_id")
                    if notification_id:
                        await self.mark_notification_as_received(notification_id)

                elif message_type == "subscribe":
                    # Client subscribing to additional groups
                    groups = data.get("groups", [])
                    for group in groups:
                        # Validate group name for security
                        if self._is_valid_group(group):
                            await self.channel_layer.group_add(group, self.channel_name)
                            logger.info(f"User {self.user_id} subscribed to group {group}")

                elif message_type == "unsubscribe":
                    # Client unsubscribing from groups
                    groups = data.get("groups", [])
                    for group in groups:
                        if self._is_valid_group(group):
                            await self.channel_layer.group_discard(group, self.channel_name)

                else:
                    logger.warning(f"Received unknown message type: {message_type}")

            elif bytes_data and hasattr(self, "handle_binary"):
                # Handle binary message (e.g., MessagePack from Swift)
                await self.handle_binary(bytes_data)

        except json.JSONDecodeError:
            logger.warning("Received invalid JSON")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def handle_binary(self, binary_data):
        """Handle binary messages (MessagePack format used by Swift)"""
        try:
            import msgpack

            data = msgpack.unpackb(binary_data)

            # Process in same way as JSON messages
            message_type = data.get("type")

            if message_type == "ping":
                # Swift ping - respond with msgpack binary pong
                response = {
                    "type": "pong",
                    "timestamp": data.get("timestamp"),
                    "client_id": data.get("client_id"),
                }
                await self.send(bytes_data=msgpack.packb(response))

            # Handle other binary message types...

        except Exception as e:
            logger.error(f"Error processing binary message: {e}")

    async def notification(self, event):
        """
        Handle notification from channel layer
        This is called when a message is broadcast to a group
        """
        try:
            message_data = event.get("data", {})
            notification_type = message_data.get("type")
            notification_id = message_data.get("id")

            # Format based on client type (iOS/Android/Web)
            if getattr(self, "is_ios", False):
                # Use Swift-compatible format for iOS
                message = SwiftCompatibleMessage.new_notification(
                    notification_id=notification_id,
                    title=message_data.get("title", ""),
                    body=message_data.get("message", ""),
                    data=message_data.get("data", {}),
                )
            else:
                # Standard format for other clients
                message = message_data

            # Send notification to client
            await send_to_client(
                self,
                "notification",
                message,
                client_id=getattr(self, "client_id", None),
            )

            # Cache that we've sent this notification to this user
            cache_key = f"notification_sent:{notification_id}:{self.user_id}"
            await database_sync_to_async(consumer_cache.set)(cache_key, True, 60 * 60)

        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def status_update(self, event):
        """Handle status update events (e.g., booking status changes)"""
        try:
            update_data = event.get("data", {})
            entity_type = update_data.get("entity_type")
            entity_id = update_data.get("entity_id")

            # Format based on client type
            if getattr(self, "is_ios", False):
                # Use Swift-compatible format
                message = SwiftCompatibleMessage.status_update(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status=update_data.get("status"),
                    details=update_data.get("details", {}),
                )
            else:
                message = update_data

            # Send status update to client
            await send_to_client(
                self,
                "status_update",
                message,
                client_id=getattr(self, "client_id", None),
            )

        except Exception as e:
            logger.error(f"Error sending status update: {e}")

    async def booking_update(self, event):
        """Handle booking update events with iOS optimization"""
        try:
            booking_data = event.get("data", {})
            booking_id = booking_data.get("booking_id")

            # Format for iOS if needed
            if getattr(self, "is_ios", False):
                message = SwiftCompatibleMessage.booking_change(
                    booking_id=booking_id,
                    change_type=booking_data.get("change_type", "update"),
                    old_status=booking_data.get("old_status"),
                    new_status=booking_data.get("new_status"),
                    details=booking_data.get("details", {}),
                )
            else:
                message = booking_data

            # Send to client with auto-compression for large payloads
            await send_to_client(
                self,
                "booking_update",
                message,
                client_id=getattr(self, "client_id", None),
            )

        except Exception as e:
            logger.error(f"Error sending booking update: {e}")

    @database_sync_to_async
    def mark_notification_as_received(self, notification_id: str) -> bool:
        """Mark a notification as received by this user"""
        try:
            # This would typically update a UserNotification model
            # For now, we'll just record in cache
            cache_key = f"notification_received:{notification_id}:{self.user_id}"
            consumer_cache.set(cache_key, True, 60 * 60 * 24)  # 24 hours
            return True
        except Exception as e:
            logger.error(f"Error marking notification as received: {e}")
            return False

    async def send_pending_notifications(self):
        """Send any pending notifications when client connects"""
        try:
            # In a real implementation, this would query pending notifications
            # that haven't been delivered yet.
            # For demonstration, just send a welcome notification

            # Only send welcome message if iOS client
            if getattr(self, "is_ios", False):
                welcome_message = SwiftCompatibleMessage.new_notification(
                    notification_id="welcome",
                    title="Welcome to QueueMe",
                    body="You are now connected to real-time notifications",
                    data={"type": "welcome"},
                )

                await send_to_client(
                    self,
                    "notification",
                    welcome_message,
                    client_id=getattr(self, "client_id", None),
                )

        except Exception as e:
            logger.error(f"Error sending pending notifications: {e}")

    def _is_valid_group(self, group_name: str) -> bool:
        """
        Validate group name for security
        Prevent subscribing to sensitive groups
        """
        # Only allow subscribing to specific group formats
        allowed_prefixes = [
            f"shop_{self.user_id}_",
            f"booking_{self.user_id}_",
            f"service_{self.user_id}_",
            "public_announcements",
        ]

        return any(group_name.startswith(prefix) for prefix in allowed_prefixes)
