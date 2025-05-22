"""
WebSocket consumer for queue status updates.

This consumer provides real-time updates about queue status, including:
- Current position in queue
- Estimated wait time
- Notifications when it's the customer's turn
"""

import json
import logging
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from apps.authapp.services.token_service import TokenService
from apps.queueapp.models import Queue, QueueTicket
from apps.queueapp.services.queue_service import QueueService

logger = logging.getLogger(__name__)


class QueueStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time queue status updates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: Optional[str] = None
        self.queue_id: Optional[str] = None
        self.queue_group_name: Optional[str] = None
        self.ticket: Optional[QueueTicket] = None

    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get token from query string
            query_string = self.scope["query_string"].decode()
            query_params = dict(
                x.split("=") for x in query_string.split("&") if "=" in x
            )
            token = query_params.get("token", "")

            if not token:
                logger.warning("Queue status connection rejected: No token provided")
                await self.close(code=4001)
                return

            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if not user:
                logger.warning("Queue status connection rejected: Invalid token")
                await self.close(code=4001)
                return

            if not user.is_active:
                logger.warning(
                    f"Queue status connection rejected: User {user.id} is inactive"
                )
                await self.close(code=4002)
                return

            self.user_id = str(user.id)

            # Get queue ID from URL
            self.queue_id = self.scope["url_route"]["kwargs"]["queue_id"]
            self.queue_group_name = f"queue_{self.queue_id}"

            # Check if user has access to this queue
            has_access = await database_sync_to_async(self.check_queue_access)()

            if not has_access:
                logger.warning(
                    f"Queue status connection rejected: User {self.user_id} has no access to queue {self.queue_id}"
                )
                await self.close(code=4003)
                return

            # Get user's ticket in this queue
            self.ticket = await database_sync_to_async(self.get_user_ticket)()

            # Join queue group
            await self.channel_layer.group_add(self.queue_group_name, self.channel_name)

            # Accept connection
            await self.accept()

            # Send initial queue status
            await self.send_queue_status()

            logger.info(
                f"Queue status connection established for user {self.user_id} to queue {self.queue_id}"
            )

        except Exception as e:
            logger.error(f"Error in queue status connection: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if self.queue_group_name:
                await self.channel_layer.group_discard(
                    self.queue_group_name, self.channel_name
                )
            logger.info(
                f"Queue status connection closed for user {self.user_id} to queue {self.queue_id}"
            )
        except Exception as e:
            logger.error(f"Error in queue status disconnection: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            else:
                logger.warning(f"Received unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.warning("Received invalid JSON data")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    async def queue_update(self, event):
        """Handle queue update events."""
        try:
            await self.send_queue_status()
        except Exception as e:
            logger.error(f"Error sending queue update: {str(e)}")

    async def send_queue_status(self):
        """Send current queue status to the client."""
        try:
            if not self.ticket:
                status = await database_sync_to_async(self.get_queue_status)()
            else:
                status = await database_sync_to_async(self.get_ticket_status)()

            await self.send(
                text_data=json.dumps(
                    {"type": "queue_status", "data": status}, cls=DjangoJSONEncoder
                )
            )
        except Exception as e:
            logger.error(f"Error sending queue status: {str(e)}")

    def check_queue_access(self):
        """Check if user has access to this queue."""
        try:
            queue = Queue.objects.get(id=self.queue_id)
            return QueueService.check_user_queue_access(self.user_id, queue)
        except Queue.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking queue access: {str(e)}")
            return False

    def get_user_ticket(self):
        """Get user's active ticket in this queue."""
        try:
            return QueueTicket.objects.filter(
                queue_id=self.queue_id,
                user_id=self.user_id,
                status__in=["waiting", "called"],
            ).first()
        except Exception as e:
            logger.error(f"Error getting user ticket: {str(e)}")
            return None

    def get_queue_status(self):
        """Get general queue status."""
        try:
            queue = Queue.objects.get(id=self.queue_id)
            return {
                "queue_id": str(queue.id),
                "name": queue.name,
                "status": queue.status,
                "current_position": None,
                "estimated_wait_time": None,
                "total_waiting": queue.get_waiting_count(),
            }
        except Queue.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting queue status: {str(e)}")
            return None

    def get_ticket_status(self):
        """Get status for user's ticket."""
        try:
            if not self.ticket:
                return self.get_queue_status()

            return {
                "queue_id": str(self.ticket.queue.id),
                "name": self.ticket.queue.name,
                "status": self.ticket.queue.status,
                "ticket_id": str(self.ticket.id),
                "ticket_number": self.ticket.ticket_number,
                "current_position": self.ticket.position,
                "estimated_wait_time": self.ticket.estimated_wait_time,
                "total_waiting": self.ticket.queue.get_waiting_count(),
            }
        except Exception as e:
            logger.error(f"Error getting ticket status: {str(e)}")
            return None
