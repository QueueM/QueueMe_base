"""
WebSocket URL routing configuration.

This module defines the WebSocket URL patterns for the Queue Me platform.
"""

from django.urls import path

from websockets.consumers.chat import ChatConsumer
from websockets.consumers.notifications import NotificationConsumer
from websockets.consumers.queue_status import QueueStatusConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    # Queue status updates
    path("ws/queue/<str:queue_id>/", QueueStatusConsumer.as_asgi()),
    # Chat communication
    path("ws/chat/<str:conversation_id>/", ChatConsumer.as_asgi()),
    # Real-time notifications
    path("ws/notifications/<str:user_id>/", NotificationConsumer.as_asgi()),
]
