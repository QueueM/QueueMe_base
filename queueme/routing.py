"""
WebSocket routing configuration for Queue Me platform.

This module defines the WebSocket routing for the platform,
including routes for real-time chat, notifications, and queue updates.
"""

from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

# Import websocket consumers
from apps.chatapp.consumers import ChatConsumer
from apps.notificationsapp.consumers import NotificationConsumer
from apps.queueapp.consumers import QueueConsumer

# Define WebSocket URL patterns
websocket_urlpatterns = [
    # Chat WebSocket - for real-time conversation between customer and shop
    path("ws/chat/<str:conversation_id>/", ChatConsumer.as_asgi()),
    # Queue WebSocket - for real-time queue status updates
    path("ws/queue/<str:shop_id>/", QueueConsumer.as_asgi()),
    # Notification WebSocket - for real-time notifications delivery
    path("ws/notifications/<str:user_id>/", NotificationConsumer.as_asgi()),
]

# Define WebSocket application with middleware
websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
)
