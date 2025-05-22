import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.authapp.services.token_service import TokenService


class StoryConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time story updates.
    Notifies customers when new stories are posted from shops they follow.
    """

    async def connect(self):
        """
        Handle WebSocket connection
        - Authenticate using token
        - Join appropriate groups based on user type
        """
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
        self.user_type = user.user_type

        # Join appropriate groups based on user type
        if self.user_type == "customer":
            # Join customer-specific group
            self.group_name = f"stories_customer_{self.user_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Also join the followed shops group if possible
            await self._join_followed_shops_group()

        elif self.user_type in ["employee", "admin"]:
            # Join appropriate shop group for staff
            shop_id = await self._get_user_shop_id()
            if shop_id:
                self.group_name = f"stories_shop_{shop_id}"
                await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        - Leave all joined groups
        """
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        # Also leave the followed shops group if customer
        if hasattr(self, "user_type") and self.user_type == "customer":
            followed_group = f"stories_followed_{self.user_id}"
            await self.channel_layer.group_discard(followed_group, self.channel_name)

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        Not used extensively as this is mostly for server->client communication
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"type": "pong", "timestamp": timezone.now().isoformat()}
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": _("Invalid JSON format")}
                )
            )

    async def story_update(self, event):
        """
        Handle story update event and send to client
        """
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "story_update",
                    "story_id": event.get("story_id"),
                    "shop_id": event.get("shop_id"),
                    "shop_name": event.get("shop_name"),
                    "action": event.get("action"),
                    "story_type": event.get("story_type"),
                    "timestamp": event.get("timestamp"),
                },
                cls=DjangoJSONEncoder,
            )
        )

    async def story_expiry(self, event):
        """
        Handle story expiry event and send to client
        """
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "story_expiry",
                    "story_id": event.get("story_id"),
                    "shop_id": event.get("shop_id"),
                }
            )
        )

    @database_sync_to_async
    def _get_user_shop_id(self):
        """Get the shop ID for an employee user"""
        if self.user_type != "employee":
            return None

        from apps.employeeapp.models import Employee

        try:
            from apps.authapp.models import User

            user = User.objects.get(id=self.user_id)
            employee = Employee.objects.get(user=user)
            return str(employee.shop_id)
        except (Employee.DoesNotExist, User.DoesNotExist):
            return None

    @database_sync_to_async
    def _join_followed_shops_group(self):
        """Join the group for followed shops updates"""

        try:
            # Get ContentType for Shop model
            pass

            # unused_unused_shop_content_type = ContentType.objects.get_for_model(Shop)
            # Create a joined group for all followed shops
            self.followed_group = f"stories_followed_{self.user_id}"
            return self.channel_layer.group_add(self.followed_group, self.channel_name)
        except Exception:
            return None
