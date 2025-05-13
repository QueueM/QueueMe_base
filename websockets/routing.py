"""
WebSocket URL routing configuration.

This module defines the WebSocket URL patterns for the Queue Me platform.
"""

from django.urls import re_path

from websockets.consumers.chat import ChatConsumer
from websockets.consumers.notifications import NotificationConsumer
from websockets.consumers.queue_consumer import QueueConsumer
from websockets.consumers.queue_status import QueueStatusConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    # Queue status updates
    re_path(r"ws/queue/(?P<queue_id>[^/]+)/$", QueueConsumer.as_asgi()),
    re_path(r"ws/shop/(?P<shop_id>[^/]+)/queues/$", QueueConsumer.as_asgi()),
    # Chat communication
    re_path(r"ws/chat/(?P<conversation_id>[^/]+)/$", ChatConsumer.as_asgi()),
    # Real-time notifications
    re_path(r"ws/notifications/(?P<user_id>[^/]+)/$", NotificationConsumer.as_asgi()),
]
