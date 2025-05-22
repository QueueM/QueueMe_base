"""
Enhanced WebSocket Consumer

Provides a robust, production-ready WebSocket consumer implementation
with advanced features like compression, heartbeats, reconnection,
and error handling.
"""

import asyncio
import inspect
import json
import logging
import time
import zlib
from functools import wraps
from typing import Any, Dict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import close_old_connections

logger = logging.getLogger(__name__)

# Default configuration with fallbacks to settings
DEFAULT_COMPRESSION_ENABLED = getattr(settings, "WEBSOCKET_COMPRESSION_ENABLED", True)
DEFAULT_COMPRESSION_THRESHOLD = getattr(
    settings, "WEBSOCKET_COMPRESSION_THRESHOLD", 1024
)  # bytes
DEFAULT_COMPRESSION_LEVEL = getattr(
    settings, "WEBSOCKET_COMPRESSION_LEVEL", 6
)  # 0-9, higher = better compression but slower
DEFAULT_HEARTBEAT_INTERVAL = getattr(
    settings, "WEBSOCKET_HEARTBEAT_INTERVAL", 30
)  # seconds
DEFAULT_CLIENT_TIMEOUT = getattr(settings, "WEBSOCKET_CLIENT_TIMEOUT", 90)  # seconds
DEFAULT_MAX_MESSAGE_SIZE = getattr(
    settings, "WEBSOCKET_MAX_MESSAGE_SIZE", 1024 * 1024
)  # bytes (1MB)
DEFAULT_RATE_LIMIT = getattr(
    settings, "WEBSOCKET_RATE_LIMIT", 60
)  # messages per minute
DEFAULT_CLOSE_TIMEOUT = getattr(settings, "WEBSOCKET_CLOSE_TIMEOUT", 5)  # seconds


class WebSocketStats:
    """
    Track WebSocket connection and message statistics
    """

    def __init__(self):
        # Connection stats
        self.connections_total = 0
        self.connections_active = 0
        self.connections_closed = 0
        self.connections_errored = 0
        self.connections_by_group = {}

        # Message stats
        self.messages_received = 0
        self.messages_sent = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.compressed_messages = 0
        self.errors = 0

        # Performance stats
        self.message_processing_time = 0  # total time
        self.message_count = 0  # count for averaging

    def get_stats(self) -> Dict[str, Any]:
        """Get all stats as a dictionary"""
        avg_processing_time = 0
        if self.message_count > 0:
            avg_processing_time = self.message_processing_time / self.message_count

        return {
            "connections": {
                "total": self.connections_total,
                "active": self.connections_active,
                "closed": self.connections_closed,
                "errored": self.connections_errored,
                "by_group": self.connections_by_group,
            },
            "messages": {
                "received": self.messages_received,
                "sent": self.messages_sent,
                "bytes_received": self.bytes_received,
                "bytes_sent": self.bytes_sent,
                "compressed": self.compressed_messages,
                "errors": self.errors,
            },
            "performance": {
                "avg_message_processing_ms": round(avg_processing_time * 1000, 2),
            },
        }


# Global stats object
websocket_stats = WebSocketStats()


def catch_errors(func):
    """
    Decorator to catch and log errors in WebSocket handler methods
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in WebSocket handler {func.__name__}: {e}")

            if hasattr(self, "channel_name"):
                # Send error message to client if possible
                try:
                    error_details = {"message": str(e)}

                    # Don't send detailed error info in production
                    if not settings.DEBUG:
                        error_details = {"message": "Internal server error"}

                    await self.send_error("internal_error", error_details)
                except Exception:
                    pass  # Ignore errors in error handling

            # Update stats
            websocket_stats.errors += 1
            return None

    return wrapper


class EnhancedConsumer(AsyncWebsocketConsumer):
    """
    Production-ready WebSocket consumer with advanced features
    """

    # Configuration defaults (can be overridden in subclasses)
    compression_enabled = DEFAULT_COMPRESSION_ENABLED
    compression_threshold = DEFAULT_COMPRESSION_THRESHOLD
    compression_level = DEFAULT_COMPRESSION_LEVEL
    heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL
    client_timeout = DEFAULT_CLIENT_TIMEOUT
    max_message_size = DEFAULT_MAX_MESSAGE_SIZE
    rate_limit = DEFAULT_RATE_LIMIT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_id = None
        self.groups = []
        self.connected = False
        self.last_client_activity = 0
        self.message_handlers = {}
        self.heartbeat_task = None
        self.message_count = 0
        self.rate_limit_last_reset = time.time()
        self.close_timeout_task = None

    async def connect(self):
        """
        Handle new WebSocket connection
        """
        close_old_connections()

        try:
            # Extract information from scope
            self.user = self.scope.get("user")
            if self.user and self.user.is_authenticated:
                self.user_id = self.user.id

            # Add to global stats
            websocket_stats.connections_total += 1
            websocket_stats.connections_active += 1

            # Accept connection
            await self.accept()

            # Register message handlers
            self._register_message_handlers()

            # Start heartbeat
            self._start_heartbeat()

            # Set last activity timestamp
            self.last_client_activity = time.time()
            self.connected = True

            # Call subclass implementation
            await self.on_connect()
        except Exception as e:
            logger.exception(f"Error during WebSocket connection: {e}")
            websocket_stats.connections_errored += 1
            await self.close(code=1011)  # Internal error
            raise

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        try:
            # Update stats
            websocket_stats.connections_active -= 1
            websocket_stats.connections_closed += 1

            # Leave any groups
            for group in self.groups:
                await self.leave_group(group)
            self.groups = []

            # Stop heartbeat
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass

            # Cancel timeout task if set
            if self.close_timeout_task:
                self.close_timeout_task.cancel()
                try:
                    await self.close_timeout_task
                except asyncio.CancelledError:
                    pass

            # Set connection state
            self.connected = False

            # Call subclass implementation
            await self.on_disconnect(close_code)

        except Exception as e:
            logger.exception(f"Error during WebSocket disconnection: {e}")
        finally:
            # Ensure database connections are properly closed
            close_old_connections()

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming WebSocket message
        """
        # Update last activity time
        self.last_client_activity = time.time()

        # Rate limiting check
        current_time = time.time()
        if current_time - self.rate_limit_last_reset > 60:
            # Reset counter every minute
            self.message_count = 0
            self.rate_limit_last_reset = current_time

        self.message_count += 1
        if self.message_count > self.rate_limit:
            logger.warning(f"Rate limit exceeded for {self.channel_name}")
            await self.send_error(
                "rate_limit_exceeded", {"message": "Too many messages"}
            )
            return

        # Process message
        start_time = time.time()

        try:
            # Update stats
            websocket_stats.messages_received += 1

            # Handle binary data (possibly compressed)
            if bytes_data:
                try:
                    # Attempt to decompress
                    decompressed = zlib.decompress(bytes_data)
                    text_data = decompressed.decode("utf-8")
                    websocket_stats.bytes_received += len(bytes_data)
                except (zlib.error, UnicodeDecodeError):
                    logger.error("Failed to decompress binary message")
                    await self.send_error(
                        "invalid_message", {"message": "Invalid binary format"}
                    )
                    return

            # Update byte count for text messages
            if text_data:
                websocket_stats.bytes_received += len(text_data)

                # Check message size
                if len(text_data) > self.max_message_size:
                    logger.warning(f"Message too large: {len(text_data)} bytes")
                    await self.send_error(
                        "message_too_large", {"message": "Message exceeds size limit"}
                    )
                    return
            else:
                await self.send_error("empty_message", {"message": "Message is empty"})
                return

            # Parse JSON
            try:
                message = json.loads(text_data)
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON message")
                await self.send_error(
                    "invalid_json", {"message": "Invalid JSON format"}
                )
                return

            # Validate message structure
            message_type = message.get("type")
            if not message_type:
                logger.error("Message missing type field")
                await self.send_error(
                    "missing_type", {"message": "Message type is required"}
                )
                return

            # Special handling for heartbeat messages
            if message_type == "heartbeat":
                await self.send_heartbeat()
                return

            # Process message by type
            await self._dispatch_message(message_type, message)

        except Exception as e:
            logger.exception(f"Error handling WebSocket message: {e}")
            websocket_stats.errors += 1
            await self.send_error(
                "internal_error", {"message": "Error processing message"}
            )
        finally:
            # Update performance stats
            processing_time = time.time() - start_time
            websocket_stats.message_processing_time += processing_time
            websocket_stats.message_count += 1

    async def on_connect(self):
        """
        Override in subclass to handle connection establishment
        """

    async def on_disconnect(self, close_code):
        """
        Override in subclass to handle disconnection
        """

    async def send_json(self, content, compress=None):
        """
        Send JSON data to the client, with optional compression

        Args:
            content: Dictionary to send as JSON
            compress: Whether to compress data (None = use default settings)
        """
        if not self.connected:
            logger.warning("Attempted to send message on closed connection")
            return

        try:
            # Convert to JSON
            text_data = json.dumps(content, cls=DjangoJSONEncoder)

            # Determine if compression is needed
            should_compress = compress
            if should_compress is None:
                should_compress = (
                    self.compression_enabled
                    and len(text_data) >= self.compression_threshold
                )

            # Update stats before sending
            websocket_stats.messages_sent += 1
            websocket_stats.bytes_sent += len(text_data)

            if should_compress:
                # Compress data
                compressed = zlib.compress(
                    text_data.encode("utf-8"), self.compression_level
                )
                websocket_stats.compressed_messages += 1

                # Send as binary
                await self.send(bytes_data=compressed)
            else:
                # Send as text
                await self.send(text_data=text_data)

        except Exception as e:
            logger.exception(f"Error sending WebSocket message: {e}")
            websocket_stats.errors += 1

    async def send_error(self, error_code, data=None):
        """
        Send an error message to the client

        Args:
            error_code: Error type identifier
            data: Additional error details
        """
        error_message = {"type": "error", "error": error_code, "data": data or {}}
        await self.send_json(error_message)

    async def join_group(self, group_name):
        """
        Join a channel group

        Args:
            group_name: Group to join
        """
        if group_name not in self.groups:
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.groups.append(group_name)

            # Update stats
            websocket_stats.connections_by_group[group_name] = (
                websocket_stats.connections_by_group.get(group_name, 0) + 1
            )

    async def leave_group(self, group_name):
        """
        Leave a channel group

        Args:
            group_name: Group to leave
        """
        if group_name in self.groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)
            self.groups.remove(group_name)

            # Update stats
            if group_name in websocket_stats.connections_by_group:
                websocket_stats.connections_by_group[group_name] -= 1
                if websocket_stats.connections_by_group[group_name] <= 0:
                    del websocket_stats.connections_by_group[group_name]

    async def send_heartbeat(self):
        """Send a heartbeat message to the client"""
        await self.send_json({"type": "heartbeat", "timestamp": int(time.time())})

    async def _dispatch_message(self, message_type, message):
        """
        Dispatch message to appropriate handler based on type

        Args:
            message_type: Type field from message
            message: Full message dictionary
        """
        # Look for a handler method
        handler = self.message_handlers.get(message_type)
        if handler:
            # Call handler with message data
            data = message.get("data", {})
            await handler(data)
        else:
            logger.warning(f"No handler for message type: {message_type}")
            await self.send_error(
                "unknown_message_type",
                {"message": f"Unknown message type: {message_type}"},
            )

    def _register_message_handlers(self):
        """
        Register all message handler methods based on naming convention
        Handlers should be named handle_<message_type>
        """
        self.message_handlers = {}

        # Find all methods matching the pattern
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("handle_"):
                msg_type = name[7:]  # Remove 'handle_' prefix
                self.message_handlers[msg_type] = method

        logger.debug(f"Registered {len(self.message_handlers)} message handlers")

    def _start_heartbeat(self):
        """Start the heartbeat and timeout monitoring"""

        async def heartbeat_coroutine():
            while True:
                try:
                    # Check if client has been inactive too long
                    if time.time() - self.last_client_activity > self.client_timeout:
                        logger.info(
                            f"Client timeout, closing connection: {self.channel_name}"
                        )
                        await self.close(code=1000)
                        return

                    # Send heartbeat
                    await self.send_heartbeat()

                    # Wait for next interval
                    await asyncio.sleep(self.heartbeat_interval)

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.exception(f"Error in heartbeat: {e}")
                    # Try to continue despite error
                    await asyncio.sleep(self.heartbeat_interval)

        self.heartbeat_task = asyncio.create_task(heartbeat_coroutine())

    async def handle_message(self, event):
        """
        Default handler for channel layer messages

        Args:
            event: Message from channel layer
        """
        message_type = event.get("type")

        # Skip internal messages (those with leading underscore)
        if message_type.startswith("_"):
            return

        # Forward message to client
        await self.send_json(event)

    async def delayed_close(self, code=1000, reason=None):
        """
        Close the connection after a brief delay
        Useful for ensuring the client receives final messages

        Args:
            code: WebSocket close code
            reason: Close reason
        """

        async def _close_after_delay():
            try:
                await asyncio.sleep(DEFAULT_CLOSE_TIMEOUT)
                await self.close(code)
            except Exception:
                pass

        self.close_timeout_task = asyncio.create_task(_close_after_delay())

    @catch_errors
    async def handle_ping(self, data):
        """
        Handle ping message from client

        Args:
            data: Message data
        """
        await self.send_json(
            {
                "type": "pong",
                "data": {"timestamp": int(time.time()), "echo": data.get("echo")},
            }
        )


class AuthenticatedConsumer(EnhancedConsumer):
    """
    WebSocket consumer that requires authentication
    """

    async def connect(self):
        """Check authentication before accepting connection"""
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection rejected")
            await self.close(code=4003)  # Custom code for authentication required
            return

        # Set user ID for convenience
        self.user_id = self.user.id

        # Accept the connection
        await super().connect()

    async def on_connect(self):
        """Add user to a personal group for targeted messages"""
        # Add to user-specific group
        user_group = f"user_{self.user_id}"
        await self.join_group(user_group)


class ShopConsumer(AuthenticatedConsumer):
    """
    WebSocket consumer for shop-specific connections
    """

    async def connect(self):
        """
        Connect to shop-specific channel
        """
        # Get shop_id from URL route
        self.shop_id = self.scope["url_route"]["kwargs"].get("shop_id")
        if not self.shop_id:
            logger.error("No shop_id provided in URL route")
            await self.close(code=4000)  # Custom code for invalid parameters
            return

        # Connect to base class
        await super().connect()

    @database_sync_to_async
    def check_shop_access(self):
        """
        Check if user has access to the shop
        Override in subclass with actual implementation

        Returns:
            Tuple of (has_access, role)
        """
        # Default implementation - override in subclass
        return True, "customer"

    async def on_connect(self):
        """
        Handle shop-specific connection setup
        """
        # First call parent implementation (adds to user group)
        await super().on_connect()

        # Check permissions for this shop
        has_access, role = await self.check_shop_access()
        if not has_access:
            logger.warning(f"User {self.user_id} denied access to shop {self.shop_id}")
            await self.send_error(
                "access_denied", {"message": "You don't have access to this shop"}
            )
            await self.close(code=4003)
            return

        # Store role
        self.role = role

        # Join shop group
        shop_group = f"shop_{self.shop_id}"
        await self.join_group(shop_group)

        # Join role-specific group
        role_group = f"shop_{self.shop_id}_{role}"
        await self.join_group(role_group)

        # Send confirmation to client
        await self.send_json(
            {
                "type": "connection_established",
                "data": {"shop_id": self.shop_id, "role": self.role},
            }
        )


class QueueConsumer(ShopConsumer):
    """
    WebSocket consumer for real-time queue updates
    """

    async def on_connect(self):
        """
        Set up queue-specific connection
        """
        await super().on_connect()

        # Get initial queue data
        queue_data = await self.get_queue_data()

        # Send initial data
        await self.send_json({"type": "queue_update", "data": queue_data})

    @database_sync_to_async
    def get_queue_data(self):
        """
        Get current queue data
        Override in subclass with actual implementation

        Returns:
            Dictionary with queue data
        """
        # Default implementation - override in subclass
        return {"message": "Queue data would be here"}

    @catch_errors
    async def handle_join_queue(self, data):
        """
        Handle request to join a queue

        Args:
            data: Client message data
        """
        # Process through service layer
        result = await self.add_to_queue(data)

        # Send confirmation
        await self.send_json({"type": "queue_join_result", "data": result})

        # Notify all clients in shop group about the update
        await self.channel_layer.group_send(
            f"shop_{self.shop_id}", {"type": "queue_updated", "user_id": self.user_id}
        )

    @database_sync_to_async
    def add_to_queue(self, data):
        """
        Add user to queue
        Override in subclass with actual implementation

        Returns:
            Result dictionary
        """
        # Default implementation - override in subclass
        return {"success": True, "message": "Added to queue"}

    async def queue_updated(self, event):
        """
        Handle queue update notification

        Args:
            event: Event data from channel layer
        """
        # Get updated queue data
        queue_data = await self.get_queue_data()

        # Send to client
        await self.send_json({"type": "queue_update", "data": queue_data})

    @catch_errors
    async def handle_leave_queue(self, data):
        """
        Handle request to leave a queue

        Args:
            data: Client message data
        """
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await self.send_error(
                "missing_parameter", {"message": "ticket_id is required"}
            )
            return

        # Process through service layer
        result = await self.remove_from_queue(ticket_id)

        # Send confirmation
        await self.send_json({"type": "queue_leave_result", "data": result})

        # Notify all clients in shop group about the update
        if result.get("success"):
            await self.channel_layer.group_send(
                f"shop_{self.shop_id}",
                {"type": "queue_updated", "user_id": self.user_id},
            )

    @database_sync_to_async
    def remove_from_queue(self, ticket_id):
        """
        Remove user from queue
        Override in subclass with actual implementation

        Returns:
            Result dictionary
        """
        # Default implementation - override in subclass
        return {"success": True, "message": "Removed from queue"}


class NotificationConsumer(AuthenticatedConsumer):
    """
    WebSocket consumer for user notifications
    """

    async def on_connect(self):
        """
        Set up notification-specific connection
        """
        await super().on_connect()

        # Get unread notifications
        notifications = await self.get_unread_notifications()

        # Send initial data
        await self.send_json(
            {
                "type": "unread_notifications",
                "data": {"count": len(notifications), "notifications": notifications},
            }
        )

    @database_sync_to_async
    def get_unread_notifications(self):
        """
        Get unread notifications for current user
        Override in subclass with actual implementation

        Returns:
            List of notification objects
        """
        # Default implementation - override in subclass
        return []

    async def new_notification(self, event):
        """
        Handle new notification event

        Args:
            event: Event data from channel layer
        """
        # Send to client
        await self.send_json(
            {"type": "new_notification", "data": event.get("notification", {})}
        )

    @catch_errors
    async def handle_mark_read(self, data):
        """
        Handle request to mark notifications as read

        Args:
            data: Client message data
        """
        notification_id = data.get("notification_id")
        if not notification_id:
            await self.send_error(
                "missing_parameter", {"message": "notification_id is required"}
            )
            return

        # Process through service layer
        result = await self.mark_notification_read(notification_id)

        # Send confirmation
        await self.send_json({"type": "notification_marked_read", "data": result})

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """
        Mark notification as read
        Override in subclass with actual implementation

        Returns:
            Result dictionary
        """
        # Default implementation - override in subclass
        return {"success": True, "notification_id": notification_id}


# Entry point for importing
__all__ = [
    "EnhancedConsumer",
    "AuthenticatedConsumer",
    "ShopConsumer",
    "QueueConsumer",
    "NotificationConsumer",
    "websocket_stats",
    "catch_errors",
]
