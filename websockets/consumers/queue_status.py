"""
WebSocket consumer for queue status updates.

This consumer provides real-time updates about queue status, including:
- Current position in queue
- Estimated wait time
- Notifications when it's the customer's turn
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.queueapp.models import Queue, QueueTicket
from apps.queueapp.services.queue_service import QueueService


class QueueStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time queue status updates."""

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

        self.user_id = str(user.id)

        # Get queue ID from URL
        self.queue_id = self.scope["url_route"]["kwargs"]["queue_id"]
        self.queue_group_name = f"queue_{self.queue_id}"

        # Check if user has access to this queue
        has_access = await database_sync_to_async(self.check_queue_access)()

        if not has_access:
            # Reject connection if user doesn't have access
            await self.close(code=4003)
            return

        # Join queue group
        await self.channel_layer.group_add(self.queue_group_name, self.channel_name)

        # Accept connection
        await self.accept()

        # Send initial queue status
        await self.send_queue_status()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave queue group
        await self.channel_layer.group_discard(self.queue_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages received from the WebSocket client."""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "refresh":
                # Client requested a refresh of queue status
                await self.send_queue_status()
            elif action == "heartbeat":
                # Respond to heartbeat to keep connection alive
                await self.send(text_data=json.dumps({"type": "heartbeat_response"}))
        except json.JSONDecodeError:
            # Invalid JSON, ignore
            pass

    async def queue_update(self, event):
        """Handle queue update events from other parts of the system."""
        # Send queue update to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "queue_update", "data": event["data"]}, cls=DjangoJSONEncoder
            )
        )

    async def customer_called(self, event):
        """Handle customer called event."""
        # Send customer called notification to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "customer_called", "data": event["data"]},
                cls=DjangoJSONEncoder,
            )
        )

    async def queue_status(self, event):
        """Handle queue status events."""
        # Send queue status to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "queue_status", "data": event["data"]}, cls=DjangoJSONEncoder
            )
        )

    async def send_queue_status(self):
        """Send current queue status to the client."""
        # Get queue status data
        queue_data = await database_sync_to_async(self.get_queue_status)()

        # Send queue status to client
        await self.send(
            text_data=json.dumps(
                {"type": "queue_status", "data": queue_data}, cls=DjangoJSONEncoder
            )
        )

    def check_queue_access(self):
        """Check if user has access to this queue."""
        from apps.authapp.models import User
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user = User.objects.get(id=self.user_id)

        # Get queue
        try:
            queue = Queue.objects.get(id=self.queue_id)
        except Queue.DoesNotExist:
            return False

        # Check if user is a customer with a ticket in this queue
        if user.user_type == "customer":
            # Check if user has a ticket in this queue
            has_ticket = QueueTicket.objects.filter(
                queue_id=self.queue_id,
                customer_id=self.user_id,
                status__in=["waiting", "called", "serving"],
            ).exists()

            return has_ticket
        else:
            # For employees/staff, check if they have permission and shop access
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user_id=self.user_id)

                # Check if queue belongs to employee's shop
                if queue.shop_id != employee.shop_id:
                    return False

                # Check if employee has queue permission
                return PermissionResolver.has_permission(user, "queue", "view")
            except Employee.DoesNotExist:
                return False

    def get_queue_status(self):
        """Get current queue status."""
        from apps.authapp.models import User

        user = User.objects.get(id=self.user_id)
        queue = Queue.objects.get(id=self.queue_id)

        result = {
            "queue_id": str(self.queue_id),
            "queue_name": queue.name,
            "queue_status": queue.status,
            "shop_name": queue.shop.name,
        }

        if user.user_type == "customer":
            # Get customer's ticket
            try:
                ticket = QueueTicket.objects.get(
                    queue_id=self.queue_id,
                    customer_id=self.user_id,
                    status__in=["waiting", "called", "serving"],
                )

                # Get number of people ahead
                people_ahead = QueueTicket.objects.filter(
                    queue=queue, position__lt=ticket.position, status="waiting"
                ).count()

                # Update estimated wait time based on current queue
                estimated_wait = QueueService.estimate_wait_time(
                    queue.id, ticket.position
                )

                # Add ticket data to result
                result.update(
                    {
                        "ticket_id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "position": ticket.position,
                        "people_ahead": people_ahead,
                        "status": ticket.status,
                        "estimated_wait_time": estimated_wait,
                        "join_time": (
                            ticket.join_time.isoformat() if ticket.join_time else None
                        ),
                        "called_time": (
                            ticket.called_time.isoformat()
                            if ticket.called_time
                            else None
                        ),
                    }
                )
            except QueueTicket.DoesNotExist:
                # No active ticket
                result.update({"has_ticket": False})
        else:
            # For staff, get all active tickets in the queue
            active_tickets = QueueTicket.objects.filter(
                queue=queue, status__in=["waiting", "called", "serving"]
            ).order_by("position")

            tickets_data = []
            for ticket in active_tickets:
                tickets_data.append(
                    {
                        "ticket_id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "customer_id": str(ticket.customer_id),
                        "customer_name": ticket.customer.phone_number,
                        "position": ticket.position,
                        "status": ticket.status,
                        "estimated_wait_time": ticket.estimated_wait_time,
                        "join_time": (
                            ticket.join_time.isoformat() if ticket.join_time else None
                        ),
                        "called_time": (
                            ticket.called_time.isoformat()
                            if ticket.called_time
                            else None
                        ),
                        "service": str(ticket.service.name) if ticket.service else None,
                    }
                )

            # Add tickets data to result
            result.update(
                {
                    "active_tickets": tickets_data,
                    "waiting_count": active_tickets.filter(status="waiting").count(),
                    "called_count": active_tickets.filter(status="called").count(),
                    "serving_count": active_tickets.filter(status="serving").count(),
                }
            )

        return result
