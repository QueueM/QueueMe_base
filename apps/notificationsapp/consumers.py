import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.authapp.services.token_service import TokenService
from apps.notificationsapp.models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get token from query string
        query_string = self.scope["query_string"].decode()
        query_params = dict(x.split("=") for x in query_string.split("&"))
        token = query_params.get("token", "")

        # Verify token and get user
        user = await database_sync_to_async(TokenService.get_user_from_token)(token)

        if not user:
            # Reject connection if token is invalid
            await self.close(code=4001)
            return

        self.user_id = str(user.id)

        # Add user to notification group
        self.notification_group_name = f"notifications_{self.user_id}"
        await self.channel_layer.group_add(
            self.notification_group_name, self.channel_name
        )

        await self.accept()

        # Send unread count on connect
        unread_count = await self.get_unread_count()
        await self.send(
            text_data=json.dumps({"type": "unread_count", "count": unread_count})
        )

    async def disconnect(self, close_code):
        # Leave notification group
        await self.channel_layer.group_discard(
            self.notification_group_name, self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type", "")

        if message_type == "mark_read":
            # Handle marking notification as read
            notification_id = data.get("notification_id")
            if notification_id:
                success = await self.mark_notification_read(notification_id)

                # Send updated unread count
                if success:
                    unread_count = await self.get_unread_count()
                    await self.send(
                        text_data=json.dumps(
                            {"type": "unread_count", "count": unread_count}
                        )
                    )

    async def notification(self, event):
        """Send notification to WebSocket"""
        # Send notification data to WebSocket
        notification_data = event["notification"]

        await self.send(
            text_data=json.dumps(
                {"type": "notification", "notification": notification_data},
                cls=DjangoJSONEncoder,
            )
        )

    async def unread_count_update(self, event):
        """Send updated unread count to WebSocket"""
        await self.send(
            text_data=json.dumps({"type": "unread_count", "count": event["count"]})
        )

    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications for this user"""
        return Notification.objects.filter(
            user_id=self.user_id, status__in=["sent", "delivered"]
        ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(
                id=notification_id, user_id=self.user_id
            )

            if notification.status in ["sent", "delivered"]:
                notification.status = "read"
                notification.read_at = timezone.now()
                notification.save()
                return True

        except Notification.DoesNotExist:
            pass

        return False
