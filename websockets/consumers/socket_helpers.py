"""
Socket Helpers for Swift Client Integration

This module provides utilities for efficient WebSocket communication
with Swift mobile clients, handling serialization, compression,
and connection management optimizations.
"""

import base64
import json
import logging
import zlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import msgpack
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

# Message compression settings
ENABLE_COMPRESSION = getattr(settings, "WEBSOCKET_COMPRESSION_ENABLED", True)
COMPRESSION_THRESHOLD = getattr(
    settings, "WEBSOCKET_COMPRESSION_THRESHOLD", 1024
)  # bytes
COMPRESSION_LEVEL = getattr(
    settings, "WEBSOCKET_COMPRESSION_LEVEL", 6
)  # 0-9, higher = more compression

# Swift compatibility settings
USE_MSGPACK = getattr(
    settings, "WEBSOCKET_USE_MSGPACK", True
)  # More efficient binary format
PING_INTERVAL = getattr(settings, "WEBSOCKET_PING_INTERVAL", 30)  # seconds


async def send_to_client(
    consumer: AsyncWebsocketConsumer,
    message_type: str,
    data: Any,
    client_id: Optional[str] = None,
    compress: bool = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send optimized message to client with optional compression

    Args:
        consumer: WebSocket consumer instance
        message_type: Type of message being sent
        data: Message data (will be serialized)
        client_id: Optional client identifier for Swift client
        compress: Whether to compress message, None for auto-detection
        metadata: Optional metadata to include with message

    Returns:
        True if message was sent successfully, False otherwise
    """
    try:
        # Prepare message
        message = {"type": message_type, "data": data}

        # Add metadata if provided
        if metadata:
            message["metadata"] = metadata

        # Add client ID if provided (helps Swift client with message routing)
        if client_id:
            message["client_id"] = client_id

        # Determine whether to use compression
        if compress is None:
            # Auto-detect based on message size
            serialized = json.dumps(message).encode("utf-8")
            should_compress = (
                ENABLE_COMPRESSION and len(serialized) >= COMPRESSION_THRESHOLD
            )
        else:
            should_compress = compress and ENABLE_COMPRESSION
            serialized = json.dumps(message).encode("utf-8")

        # Apply compression if needed
        if should_compress:
            compressed = zlib.compress(serialized, COMPRESSION_LEVEL)
            encoded = base64.b64encode(compressed).decode("ascii")

            await consumer.send(
                text_data=json.dumps({"compressed": True, "data": encoded})
            )
        elif USE_MSGPACK:
            # Use binary msgpack format for efficiency (supported by Swift MessagePack libraries)
            binary_data = msgpack.packb(message, use_bin_type=True)
            await consumer.send(bytes_data=binary_data)
        else:
            # Standard JSON for maximum compatibility
            await consumer.send(text_data=json.dumps(message))

        return True

    except Exception as e:
        logger.error(f"Error sending message to client: {e}")
        return False


async def send_bulk_to_clients(
    consumer: AsyncWebsocketConsumer,
    client_ids: List[str],
    message_type: str,
    data: Any,
    compress: bool = None,
) -> Dict[str, bool]:
    """
    Send message to multiple clients efficiently

    Args:
        consumer: WebSocket consumer instance
        client_ids: List of client IDs to send to
        message_type: Type of message being sent
        data: Message data (will be serialized)
        compress: Whether to compress message, None for auto-detect

    Returns:
        Dictionary mapping client IDs to success status
    """
    results = {}

    # If data is the same for all clients, prepare it once
    base_message = {"type": message_type, "data": data}

    # Determine compression once
    if compress is None:
        serialized = json.dumps(base_message).encode("utf-8")
        should_compress = (
            ENABLE_COMPRESSION and len(serialized) >= COMPRESSION_THRESHOLD
        )
    else:
        should_compress = compress and ENABLE_COMPRESSION
        serialized = json.dumps(base_message).encode("utf-8")

    # Prepare compressed data if needed (only once)
    common_encoded = None
    if should_compress:
        compressed = zlib.compress(serialized, COMPRESSION_LEVEL)
        common_encoded = base64.b64encode(compressed).decode("ascii")

    # Send to each client
    for client_id in client_ids:
        try:
            # Clone base message and add client-specific ID
            message = base_message.copy()
            message["client_id"] = client_id

            if should_compress:
                # Use pre-compressed data
                await consumer.send(
                    text_data=json.dumps({"compressed": True, "data": common_encoded})
                )
            elif USE_MSGPACK:
                # Repack with client ID
                binary_data = msgpack.packb(message, use_bin_type=True)
                await consumer.send(bytes_data=binary_data)
            else:
                await consumer.send(text_data=json.dumps(message))

            results[client_id] = True

        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            results[client_id] = False

    return results


@database_sync_to_async
def get_client_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get client preferences for a user (async-compatible)

    Args:
        user_id: User ID

    Returns:
        Client preferences dictionary
    """
    try:
        from apps.authapp.models import User

        user = User.objects.get(id=user_id)

        # Check if user has customer profile with preferences
        preferences = {}

        if hasattr(user, "customer") and user.customer:
            # Get customer preferences
            customer = user.customer

            # Determine mobile app platform (iOS/Android)
            if hasattr(customer, "app_platform"):
                preferences["platform"] = customer.app_platform

            # Get client language preference
            if hasattr(customer, "language"):
                preferences["language"] = customer.language

            # Get notification preferences
            if hasattr(customer, "notification_preferences"):
                preferences["notifications"] = customer.notification_preferences

            # Get app version for compatibility handling
            if hasattr(customer, "app_version"):
                preferences["app_version"] = customer.app_version

        # Add defaults for missing values
        if "platform" not in preferences:
            # Check user agent from last login if available
            if hasattr(user, "last_login_user_agent"):
                ua = user.last_login_user_agent or ""
                if "iPhone" in ua or "iPad" in ua:
                    preferences["platform"] = "ios"
                elif "Android" in ua:
                    preferences["platform"] = "android"
                else:
                    preferences["platform"] = "unknown"
            else:
                preferences["platform"] = "unknown"

        if "language" not in preferences:
            preferences["language"] = user.language or "ar"  # Default to Arabic

        return preferences

    except Exception as e:
        logger.error(f"Error getting client preferences for user {user_id}: {e}")
        return {
            "platform": "unknown",
            "language": "ar",
            "notifications": {"enabled": True},
            "error": str(e),
        }


class SwiftCompatibleMessage:
    """Helper class for constructing Swift-compatible WebSocket messages"""

    @staticmethod
    def new_notification(
        notification_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a notification message compatible with iOS"""
        return {
            "notification_id": notification_id,
            "aps": {"alert": {"title": title, "body": body}, "sound": "default"},
            "data": data or {},
        }

    @staticmethod
    def status_update(
        entity_type: str,
        entity_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a status update message compatible with iOS"""
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": status,
            "details": details or {},
            "timestamp": int(datetime.now().timestamp()),
        }

    @staticmethod
    def booking_change(
        booking_id: str,
        change_type: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a booking change message compatible with iOS"""
        return {
            "booking_id": booking_id,
            "change_type": change_type,
            "old_status": old_status,
            "new_status": new_status,
            "details": details or {},
            "timestamp": int(datetime.now().timestamp()),
        }


class SwiftPingMiddleware:
    """
    Middleware to handle Swift client ping-pong for connection maintenance
    iOS apps need regular ping-pong to keep WebSocket connections alive through
    cellular network transitions and app backgrounding
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Check if this is a WebSocket connection
        if scope["type"] != "websocket":
            return await self.inner(scope, receive, send)

        # Create a wrapper for receive to intercept ping messages
        async def receive_wrapper():
            message = await receive()

            # Handle Swift ping messages
            if message["type"] == "websocket.receive":
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "ping":
                            # iOS client ping received, send pong immediately
                            client_id = data.get("client_id")
                            await send(
                                {
                                    "type": "websocket.send",
                                    "text": json.dumps(
                                        {
                                            "type": "pong",
                                            "client_id": client_id,
                                            "timestamp": data.get("timestamp"),
                                        }
                                    ),
                                }
                            )
                    except json.JSONDecodeError:
                        pass

            return message

        # Pass modified scope to inner application
        return await self.inner(scope, receive_wrapper, send)
