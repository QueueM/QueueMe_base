import json
import logging
import traceback
from datetime import datetime

from channels.db import database_sync_to_async
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService

from .services.queue_service import QueueService

logger = logging.getLogger(__name__)


class QueueConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time queue updates with error handling"""

    async def connect(self):
        """
        Handle WebSocket connection with robust error handling
        Authenticates user and subscribes to queue updates
        """
        try:
            # Get queue_id from URL route
            self.queue_id = self.scope["url_route"]["kwargs"]["queue_id"]
            self.queue_group_name = f"queue_{self.queue_id}"
            self.user_id = None  # Will be set after authentication
            self.ping_timeout = 30  # Seconds until we consider connection dead

            # Get token from query string
            query_string = self.scope["query_string"].decode()
            query_params = {}

            try:
                if query_string:
                    query_params = dict(x.split("=") for x in query_string.split("&") if "=" in x)
            except Exception as e:
                logger.warning(f"Error parsing query params: {str(e)}")
                await self.close(code=4000)
                return

            token = query_params.get("token", "")

            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if not user:
                # Reject connection if token is invalid
                logger.warning(f"Invalid token for queue connection: {token[:10]}...")
                await self.close(code=4001)
                return

            self.user_id = str(user.id)

            # Check if user has access to this queue
            has_access = await database_sync_to_async(self.check_queue_access)(
                user.id, self.queue_id
            )

            if not has_access:
                # Reject connection if user doesn't have access
                logger.warning(f"User {self.user_id} denied access to queue {self.queue_id}")
                await self.close(code=4003)
                return

            # Join queue group
            await self.channel_layer.group_add(self.queue_group_name, self.channel_name)
            await self.accept()

            # Log successful connection
            logger.info(f"User {self.user_id} connected to queue {self.queue_id}")

            # Send current queue state on connect
            queue_state = await database_sync_to_async(self.get_queue_state)()

            if "error" in queue_state:
                logger.error(f"Error retrieving queue state: {queue_state['error']}")
                await self.send_error("Failed to retrieve queue state")
            else:
                await self.send(
                    text_data=json.dumps(
                        {"type": "queue_state", "data": queue_state},
                        cls=DjangoJSONEncoder,
                    )
                )

            # Set up periodic ping to keep connection alive
            self.ping_job = self.channel_layer.loop.create_task(self.periodic_ping())

        except Exception as e:
            logger.error(f"Error in WebSocket connect: {str(e)}")
            logger.error(traceback.format_exc())
            await self.close(code=4500)

    async def periodic_ping(self):
        """Send periodic pings to keep connection alive."""
        import asyncio

        try:
            while True:
                await asyncio.sleep(20)  # Send ping every 20 seconds
                await self.send(
                    text_data=json.dumps({"type": "ping", "timestamp": datetime.now().isoformat()})
                )
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
        except Exception as e:
            logger.error(f"Error in periodic ping: {str(e)}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection with cleanup"""
        try:
            # Cancel ping task if exists
            if hasattr(self, "ping_job"):
                self.ping_job.cancel()

            # Leave queue group
            if hasattr(self, "queue_group_name") and hasattr(self, "channel_name"):
                await self.channel_layer.group_discard(self.queue_group_name, self.channel_name)

            # Log disconnection with code
            logger.info(
                f"User {getattr(self, 'user_id', 'unknown')} disconnected from queue "
                f"{getattr(self, 'queue_id', 'unknown')} with code {close_code}"
            )

        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {str(e)}")

        # Ensure consumer is properly stopped
        raise StopConsumer()

    async def receive(self, text_data):
        """Handle incoming WebSocket messages with error handling"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Handle pong response (client response to our ping)
            if message_type == "pong":
                return

            # Process message based on type
            if message_type == "join_queue":
                await self.handle_join_queue(data)
            elif message_type == "call_next":
                await self.handle_call_next(data)
            elif message_type == "mark_serving":
                await self.handle_mark_serving(data)
            elif message_type == "mark_served":
                await self.handle_mark_served(data)
            elif message_type == "cancel_ticket":
                await self.handle_cancel_ticket(data)
            elif message_type == "get_queue_state":
                await self.handle_get_queue_state()
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            logger.error(traceback.format_exc())
            await self.send_error("Server error processing your request")

    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    async def handle_join_queue(self, data):
        """Handle customer joining the queue"""
        customer_id = data.get("customer_id")
        service_id = data.get("service_id")

        if customer_id:
            try:
                result = await database_sync_to_async(QueueService.join_queue)(
                    self.queue_id, customer_id, service_id
                )

                if isinstance(result, dict) and "error" in result:
                    await self.send_error(result["error"])
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
            except Exception as e:
                logger.error(f"Error joining queue: {str(e)}")
                await self.send_error("Failed to join queue")

    async def handle_call_next(self, data):
        """Handle staff calling next customer"""
        specialist_id = data.get("specialist_id")

        try:
            result = await database_sync_to_async(QueueService.call_next)(
                self.queue_id, specialist_id
            )

            if isinstance(result, dict) and "error" in result:
                await self.send_error(result["error"])
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
        except Exception as e:
            logger.error(f"Error calling next customer: {str(e)}")
            await self.send_error("Failed to call next customer")

    async def handle_mark_serving(self, data):
        """Handle marking customer as being served"""
        ticket_id = data.get("ticket_id")
        specialist_id = data.get("specialist_id")

        try:
            result = await database_sync_to_async(QueueService.mark_serving)(
                ticket_id, specialist_id
            )

            if isinstance(result, dict) and "error" in result:
                await self.send_error(result["error"])
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
        except Exception as e:
            logger.error(f"Error marking as serving: {str(e)}")
            await self.send_error("Failed to mark customer as serving")

    async def handle_mark_served(self, data):
        """Handle marking customer as served (completed)"""
        ticket_id = data.get("ticket_id")

        try:
            result = await database_sync_to_async(QueueService.mark_served)(ticket_id)

            if isinstance(result, dict) and "error" in result:
                await self.send_error(result["error"])
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
        except Exception as e:
            logger.error(f"Error marking as served: {str(e)}")
            await self.send_error("Failed to mark customer as served")

    async def handle_cancel_ticket(self, data):
        """Handle canceling a queue ticket"""
        ticket_id = data.get("ticket_id")

        try:
            result = await database_sync_to_async(QueueService.cancel_ticket)(ticket_id)

            if isinstance(result, dict) and "error" in result:
                await self.send_error(result["error"])
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
        except Exception as e:
            logger.error(f"Error canceling ticket: {str(e)}")
            await self.send_error("Failed to cancel ticket")

    async def handle_get_queue_state(self):
        """Handle request for current queue state"""
        try:
            queue_state = await database_sync_to_async(self.get_queue_state)()
            if "error" in queue_state:
                await self.send_error(queue_state["error"])
            else:
                await self.send(
                    text_data=json.dumps(
                        {"type": "queue_state", "data": queue_state},
                        cls=DjangoJSONEncoder,
                    )
                )
        except Exception as e:
            logger.error(f"Error getting queue state: {str(e)}")
            await self.send_error("Failed to retrieve queue state")

    async def queue_update(self, event):
        """Send queue update to WebSocket"""
        try:
            await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"Error sending queue update: {str(e)}")

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

                except Exception as e:
                    logger.warning(f"Error checking customer city: {str(e)}")
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
                except Exception as e:
                    logger.warning(f"Error checking employee shop: {str(e)}")
                    return False

            # If admin, check if has proper permission
            if user.user_type == "admin":
                # Check if user has permission to view queues
                return PermissionResolver.has_permission(user, "queue", "view")

            return False

        except Exception as e:
            logger.error(f"Error checking queue access: {str(e)}")
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
                        "service_id": (str(ticket.service_id) if ticket.service_id else None),
                        "specialist_id": (
                            str(ticket.specialist_id) if ticket.specialist_id else None
                        ),
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
                    "current_load": len(tickets),
                },
                "active_tickets": tickets,
                "waiting_count": len([t for t in tickets if t["status"] == "waiting"]),
                "called_count": len([t for t in tickets if t["status"] == "called"]),
                "serving_count": len([t for t in tickets if t["status"] == "serving"]),
                "timestamp": datetime.now().isoformat(),
            }
        except Queue.DoesNotExist:
            return {"error": f"Queue with ID {self.queue_id} not found"}
        except Exception as e:
            logger.error(f"Error getting queue state: {str(e)}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}
