import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService

from .services.queue_service import QueueService


class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get queue_id from URL route
        self.queue_id = self.scope["url_route"]["kwargs"]["queue_id"]
        self.queue_group_name = f"queue_{self.queue_id}"

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

        # Check if user has access to this queue
        has_access = await database_sync_to_async(self.check_queue_access)(
            user.id, self.queue_id
        )

        if not has_access:
            # Reject connection if user doesn't have access
            await self.close(code=4003)
            return

        # Join queue group
        await self.channel_layer.group_add(self.queue_group_name, self.channel_name)

        await self.accept()

        # Send current queue state on connect
        queue_state = await database_sync_to_async(self.get_queue_state)()
        await self.send(
            text_data=json.dumps(
                {"type": "queue_state", "data": queue_state}, cls=DjangoJSONEncoder
            )
        )

    async def disconnect(self, close_code):
        # Leave queue group
        await self.channel_layer.group_discard(self.queue_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type", "")

        if message_type == "join_queue":
            # Handle customer joining the queue
            customer_id = data.get("customer_id")
            service_id = data.get("service_id")

            if customer_id:
                result = await database_sync_to_async(QueueService.join_queue)(
                    self.queue_id, customer_id, service_id
                )

                if isinstance(result, dict) and "error" in result:
                    await self.send(
                        text_data=json.dumps(
                            {"type": "error", "message": result["error"]}
                        )
                    )
                else:
                    # Broadcast the updated queue to everyone
                    await self.channel_layer.group_send(
                        self.queue_group_name,
                        {
                            "type": "queue_update",
                            "action": "join",
                            "ticket": {
                                "id": str(result.id),
                                "ticket_number": result.ticket_number,
                                "customer_id": str(result.customer_id),
                                "position": result.position,
                                "estimated_wait_time": result.estimated_wait_time,
                                "status": result.status,
                            },
                        },
                    )

        elif message_type == "call_next":
            # Handle staff calling next customer
            specialist_id = data.get("specialist_id")

            result = await database_sync_to_async(QueueService.call_next)(
                self.queue_id, specialist_id
            )

            if isinstance(result, dict) and "error" in result:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": result["error"]})
                )
            else:
                # Broadcast the called customer
                await self.channel_layer.group_send(
                    self.queue_group_name,
                    {
                        "type": "queue_update",
                        "action": "call",
                        "ticket": {
                            "id": str(result.id),
                            "ticket_number": result.ticket_number,
                            "customer_id": str(result.customer_id),
                            "status": result.status,
                        },
                    },
                )

        elif message_type == "mark_serving":
            # Handle marking customer as being served
            ticket_id = data.get("ticket_id")
            specialist_id = data.get("specialist_id")

            result = await database_sync_to_async(QueueService.mark_serving)(
                ticket_id, specialist_id
            )

            if isinstance(result, dict) and "error" in result:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": result["error"]})
                )
            else:
                # Broadcast the status update
                await self.channel_layer.group_send(
                    self.queue_group_name,
                    {
                        "type": "queue_update",
                        "action": "serve",
                        "ticket": {
                            "id": str(result.id),
                            "ticket_number": result.ticket_number,
                            "status": result.status,
                            "actual_wait_time": result.actual_wait_time,
                        },
                    },
                )

        elif message_type == "mark_served":
            # Handle marking customer as served (completed)
            ticket_id = data.get("ticket_id")

            result = await database_sync_to_async(QueueService.mark_served)(ticket_id)

            if isinstance(result, dict) and "error" in result:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": result["error"]})
                )
            else:
                # Broadcast the completion
                await self.channel_layer.group_send(
                    self.queue_group_name,
                    {
                        "type": "queue_update",
                        "action": "complete",
                        "ticket": {
                            "id": str(result.id),
                            "ticket_number": result.ticket_number,
                            "status": result.status,
                        },
                    },
                )

        elif message_type == "cancel_ticket":
            # Handle canceling a queue ticket
            ticket_id = data.get("ticket_id")

            result = await database_sync_to_async(QueueService.cancel_ticket)(ticket_id)

            if isinstance(result, dict) and "error" in result:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": result["error"]})
                )
            else:
                # Broadcast the cancellation
                await self.channel_layer.group_send(
                    self.queue_group_name,
                    {
                        "type": "queue_update",
                        "action": "cancel",
                        "ticket": {
                            "id": str(result.id),
                            "ticket_number": result.ticket_number,
                            "status": result.status,
                        },
                    },
                )

        elif message_type == "get_queue_state":
            # Handle request for current queue state
            queue_state = await database_sync_to_async(self.get_queue_state)()
            await self.send(
                text_data=json.dumps(
                    {"type": "queue_state", "data": queue_state}, cls=DjangoJSONEncoder
                )
            )

    async def queue_update(self, event):
        # Send queue update to WebSocket
        await self.send(text_data=json.dumps(event))

    def check_queue_access(self, user_id, queue_id):
        """Check if user has access to this queue"""
        from apps.authapp.models import User
        from apps.queueapp.models import Queue
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        try:
            queue = Queue.objects.get(id=queue_id)
            user = User.objects.get(id=user_id)

            # If customer, check if same city
            if user.user_type == "customer":
                # Get customer's city
                try:
                    from apps.customersapp.models import Customer

                    customer = Customer.objects.get(user=user)
                    customer_city = customer.city

                    # Get shop's city
                    shop_city = queue.shop.location.city

                    # Customer can only access queues in same city
                    if customer_city != shop_city:
                        return False

                    return True

                except Exception:
                    # If can't determine city, default to allow
                    return True

            # If employee/shop manager/admin, check if has permission
            # Employees can only access their shop's queues
            if user.user_type == "employee":
                try:
                    from apps.employeeapp.models import Employee

                    employee = Employee.objects.get(user=user)

                    # Check if employee belongs to the shop that owns this queue
                    if employee.shop_id == queue.shop_id:
                        return True

                    return False
                except Exception:
                    return False

            # If admin, check if has proper permission
            if user.user_type == "admin":
                # Check if user has permission to view queues
                return PermissionResolver.has_permission(user, "queue", "view")

            return False

        except Exception:
            return False

    def get_queue_state(self):
        """Get current state of the queue"""
        from apps.queueapp.models import Queue, QueueTicket

        try:
            queue = Queue.objects.get(id=self.queue_id)

            # Get active tickets in the queue (waiting, called, or serving)
            active_tickets = QueueTicket.objects.filter(
                queue=queue, status__in=["waiting", "called", "serving"]
            ).order_by("position")

            # Serialize ticket data
            tickets = []
            for ticket in active_tickets:
                tickets.append(
                    {
                        "id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "customer_id": str(ticket.customer_id),
                        "status": ticket.status,
                        "position": ticket.position,
                        "estimated_wait_time": ticket.estimated_wait_time,
                        "join_time": ticket.join_time,
                        "called_time": ticket.called_time,
                        "serve_time": ticket.serve_time,
                    }
                )

            return {
                "queue": {
                    "id": str(queue.id),
                    "name": queue.name,
                    "shop_id": str(queue.shop_id),
                    "status": queue.status,
                    "max_capacity": queue.max_capacity,
                },
                "active_tickets": tickets,
                "waiting_count": len([t for t in tickets if t["status"] == "waiting"]),
                "called_count": len([t for t in tickets if t["status"] == "called"]),
                "serving_count": len([t for t in tickets if t["status"] == "serving"]),
            }
        except Exception as e:
            return {"error": str(e)}
