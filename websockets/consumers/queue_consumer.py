"""
Queue WebSocket Consumer

A WebSocket consumer for real-time queue updates, with optimizations for
performance and scalability.
"""

import json
import logging
import zlib

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

logger = logging.getLogger(__name__)


class QueueConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time queue updates.

    Features:
    - Authentication and permission checking
    - Message compression
    - Group management for efficient broadcasting
    - Rate limiting and flood protection
    """

    # Message rate limiting
    MAX_MESSAGES_PER_MINUTE = 60

    # Stream compression level (0-9, higher = more compression)
    COMPRESSION_LEVEL = 5

    async def connect(self):
        """Handle WebSocket connection."""
        # Get the user from the scope
        self.user = self.scope["user"]

        # Get the queue ID from the URL
        self.queue_id = self.scope["url_route"]["kwargs"].get("queue_id")
        self.shop_id = self.scope["url_route"]["kwargs"].get("shop_id")

        # Track message rate for flood protection
        self.message_count = 0
        self.last_message_time = timezone.now()

        # Set up compression if requested
        self.use_compression = (
            self.scope.get("query_string", b"").find(b"compression=true") >= 0
        )

        # Check authentication for protected queues
        if not self.queue_id and not self.shop_id:
            # Neither queue_id nor shop_id provided
            await self.close(code=4000)
            return

        if self.queue_id:
            # For queue-specific updates
            if not await self._has_queue_access():
                await self.close(code=4003)
                return

            # Join the specific queue group
            self.group_name = f"queue_{self.queue_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)

        if self.shop_id:
            # For shop-wide queue updates
            if not await self._has_shop_access():
                await self.close(code=4003)
                return

            # Join the shop queues group
            self.shop_group_name = f"shop_queues_{self.shop_id}"
            await self.channel_layer.group_add(self.shop_group_name, self.channel_name)

        # Accept the connection
        await self.accept()

        # Send initial state
        if self.queue_id:
            await self._send_queue_status()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave the queue group
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        # Leave the shop group
        if hasattr(self, "shop_group_name"):
            await self.channel_layer.group_discard(
                self.shop_group_name, self.channel_name
            )

    async def receive_json(self, content):
        """Handle incoming messages."""
        # Rate limiting
        current_time = timezone.now()
        time_diff = (current_time - self.last_message_time).total_seconds()

        if time_diff < 60:  # Within a minute window
            self.message_count += 1
            if self.message_count > self.MAX_MESSAGES_PER_MINUTE:
                logger.warning(
                    f"Rate limit exceeded for user {self.user.id if not isinstance(self.user, AnonymousUser) else 'anonymous'}"
                )
                # Don't process this message
                return
        else:
            # Reset counter for new minute
            self.message_count = 1
            self.last_message_time = current_time

        # Handle message based on type
        message_type = content.get("type")

        if message_type == "request_status":
            await self._send_queue_status()
        elif message_type == "ping":
            await self.send_json(
                {"type": "pong", "timestamp": timezone.now().isoformat()}
            )

    async def queue_update(self, event):
        """Handle queue update messages from the channel layer."""
        # Extract the message data
        message = event.get("message", {})

        # Send the message to the WebSocket
        if self.use_compression:
            # Compress the message for bandwidth optimization
            json_data = json.dumps(message)
            compressed_data = zlib.compress(json_data.encode(), self.COMPRESSION_LEVEL)
            await self.send(bytes_data=compressed_data)
        else:
            # Send as regular JSON
            await self.send_json(message)

    async def specialist_update(self, event):
        """Handle specialist status updates."""
        # Only send if this is for the same shop
        if event.get("shop_id") == self.shop_id:
            # Send the message to the WebSocket
            await self.send_json(event.get("message", {}))

    async def position_update(self, event):
        """Handle customer position updates."""
        # Check if update applies to this queue
        if event.get("queue_id") == self.queue_id:
            await self.send_json(event.get("message", {}))

    # Private helper methods

    @database_sync_to_async
    def _has_queue_access(self):
        """Check if user has access to the queue."""
        # Anonymous access for public queues
        if isinstance(self.user, AnonymousUser):
            # Default policy: public queues are accessible
            return True

        # For authenticated users, check permissions
        # Add your permission logic here
        return True

    @database_sync_to_async
    def _has_shop_access(self):
        """Check if user has access to shop-wide queue updates."""
        # Staff members need to be authenticated
        if isinstance(self.user, AnonymousUser):
            return False

        # Check if user has staff access to this shop
        # Add your permission logic here

        # Default admin/staff check
        return self.user.is_staff or self.user.is_superuser

    @database_sync_to_async
    def _get_queue_status(self):
        """Get the current status of the queue."""
        from apps.queueapp.services.queue_manager import QueueManager

        # Use the queue manager service
        status = QueueManager.get_queue_status(self.queue_id)
        return status

    async def _send_queue_status(self):
        """Send current queue status to the client."""
        # Get current status
        status = await self._get_queue_status()

        # Send it to the client
        await self.send_json(
            {
                "type": "queue_status",
                "status": status,
                "timestamp": timezone.now().isoformat(),
            }
        )
