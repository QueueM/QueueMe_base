import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils.translation import gettext_lazy as _

from apps.authapp.services.token_service import TokenService


class SpecialistStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for specialist real-time status updates"""

    async def connect(self):
        """Handle connection - authenticate and join appropriate group"""
        # Get token from query string
        query_string = self.scope["query_string"].decode()
        query_params = dict(x.split("=") for x in query_string.split("&"))
        token = query_params.get("token", "")

        # Authenticate token
        user = await database_sync_to_async(TokenService.get_user_from_token)(token)

        if not user:
            # Authentication failed
            await self.close(code=4001)
            return

        self.user_id = str(user.id)

        # Get specialist ID from URL route
        self.specialist_id = self.scope["url_route"]["kwargs"]["specialist_id"]

        # Check if user has permission to receive updates for this specialist
        has_permission = await database_sync_to_async(self.check_permission)()

        if not has_permission:
            await self.close(code=4003)
            return

        # Join specialist group
        self.group_name = f"specialist_{self.specialist_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """Handle disconnect - leave group"""
        # Leave specialist group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages received from WebSocket"""
        # Staff can send status updates for the specialist
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "status_update":
                # Check if user has permission to update status
                is_staff = await database_sync_to_async(self.check_staff_permission)()

                if not is_staff:
                    await self.send(
                        json.dumps(
                            {
                                "type": "error",
                                "message": _(
                                    "You do not have permission to update specialist status."
                                ),
                            }
                        )
                    )
                    return

                # Process status update
                status = data.get("status")

                # Broadcast status update to the group
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "status_update",
                        "status": status,
                        "updated_by": self.user_id,
                    },
                )
        except json.JSONDecodeError:
            await self.send(
                json.dumps({"type": "error", "message": _("Invalid message format.")})
            )

    async def status_update(self, event):
        """Handle status update event - send to WebSocket"""
        # Send update to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "status_update",
                    "status": event["status"],
                    "updated_by": event["updated_by"],
                }
            )
        )

    async def appointment_update(self, event):
        """Handle appointment update event - send to WebSocket"""
        # Send update to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "appointment_update",
                    "appointment": event["appointment"],
                    "status": event["status"],
                }
            )
        )

    def check_permission(self):
        """Check if user has permission to receive updates for this specialist"""
        from django.shortcuts import get_object_or_404

        from apps.authapp.models import User
        from apps.rolesapp.services.permission_resolver import PermissionResolver
        from apps.specialistsapp.models import Specialist

        user = User.objects.get(id=self.user_id)
        specialist = get_object_or_404(Specialist, id=self.specialist_id)

        # Queue Me admins or employees with proper permissions
        if PermissionResolver.has_permission(user, "specialist", "view"):
            return True

        # Shop staff can view their own specialists
        if user.user_type in ["employee", "admin"]:
            try:
                employee = user.employee
                return employee.shop_id == specialist.employee.shop_id
            except Exception:
                pass

        # For customers, specialist must be active and from active shop
        return specialist.employee.is_active and specialist.employee.shop.is_active

    def check_staff_permission(self):
        """Check if user has permission to update specialist status"""
        from django.shortcuts import get_object_or_404

        from apps.authapp.models import User
        from apps.rolesapp.services.permission_resolver import PermissionResolver
        from apps.specialistsapp.models import Specialist

        user = User.objects.get(id=self.user_id)
        specialist = get_object_or_404(Specialist, id=self.specialist_id)

        # Queue Me admins or employees with proper permissions
        if PermissionResolver.has_permission(user, "specialist", "edit"):
            return True

        # Shop staff can manage their own specialists
        if user.user_type in ["employee", "admin"]:
            try:
                employee = user.employee
                if employee.shop_id == specialist.employee.shop_id:
                    return PermissionResolver.has_shop_permission(
                        user, str(employee.shop_id), "specialist", "edit"
                    )
            except Exception:
                pass

        # The specialist's own employee can update status
        if hasattr(user, "employee") and user.employee.id == specialist.employee.id:
            return True

        return False
