"""
WebSocket consumer for real-time notifications.

This consumer provides real-time notifications to users for various events.
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.notificationsapp.models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""

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

        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]

        # Verify user_id from token matches user_id from URL
        if str(user.id) != self.user_id:
            # Reject connection if user_id doesn't match
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

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave notification group
        await self.channel_layer.group_discard(
            self.notification_group_name, self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages received from the WebSocket client."""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "mark_read":
                # Mark notification as read
                notification_id = data.get("notification_id")
                if notification_id:
                    await database_sync_to_async(self.mark_notification_read)(
                        notification_id
                    )

                    # Send updated unread count
                    await self.send_unread_count()
            elif action == "mark_all_read":
                # Mark all notifications as read
                await database_sync_to_async(self.mark_all_read)()

                # Send updated unread count
                await self.send_unread_count()
            elif action == "get_unread_count":
                # Send unread notification count
                await self.send_unread_count()
            elif action == "heartbeat":
                # Respond to heartbeat to keep connection alive
                await self.send(text_data=json.dumps({"type": "heartbeat_response"}))
        except json.JSONDecodeError:
            # Invalid JSON, ignore
            pass

    async def notification_event(self, event):
        """Handle notification events."""
        # Send notification to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "notification", "notification": event["notification"]},
                cls=DjangoJSONEncoder,
            )
        )

        # Send updated unread count
        await self.send_unread_count()

    async def unread_count(self, event):
        """Handle unread count updates."""
        # Send unread count to WebSocket
        await self.send(
            text_data=json.dumps({"type": "unread_count", "count": event["count"]})
        )

    async def send_unread_count(self):
        """Send current unread notification count to the client."""
        # Get unread count
        count = await database_sync_to_async(self.get_unread_count)()

        # Send unread count to client
        await self.send(text_data=json.dumps({"type": "unread_count", "count": count}))

    def mark_notification_read(self, notification_id):
        """Mark a notification as read."""
        from django.utils import timezone

        try:
            notification = Notification.objects.get(
                id=notification_id,
                user_id=self.user_id,
                status__in=["pending", "sent", "delivered"],
            )

            notification.status = "read"
            notification.read_at = timezone.now()
            notification.save()

            return True
        except Notification.DoesNotExist:
            return False

    def mark_all_read(self):
        """Mark all notifications for the user as read."""
        from django.utils import timezone

        # Get unread notifications
        notifications = Notification.objects.filter(
            user_id=self.user_id, status__in=["pending", "sent", "delivered"]
        )

        # Mark all as read
        count = notifications.count()
        now = timezone.now()

        notifications.update(status="read", read_at=now)

        return count

    def get_unread_count(self):
        """Get count of unread notifications for the user."""
        return Notification.objects.filter(
            user_id=self.user_id, status__in=["pending", "sent", "delivered"]
        ).count()
