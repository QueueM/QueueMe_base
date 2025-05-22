"""
WebSocket URL routing configuration.

This module defines the WebSocket URL patterns for the Queue Me platform.
"""

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path, re_path

from websockets.consumers.admin_dashboard import BookingStatsConsumer
from websockets.consumers.chat import ChatConsumer
from websockets.consumers.notifications import NotificationConsumer
from websockets.consumers.queue_consumer import QueueConsumer

from . import consumers
from .consumers.analytics_consumer import AdminDashboardConsumer, AnalyticsConsumer
from .consumers.booking_consumer import BookingStatusConsumer
from .consumers.notifications_consumer import NotificationsConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    # Queue status updates
    re_path(r"ws/queue/(?P<queue_id>[^/]+)/$", QueueConsumer.as_asgi()),
    re_path(r"ws/shop/(?P<shop_id>[^/]+)/queues/$", QueueConsumer.as_asgi()),
    # Chat communication
    re_path(r"ws/chat/(?P<conversation_id>[^/]+)/$", ChatConsumer.as_asgi()),
    # Real-time notifications
    re_path(r"ws/notifications/(?P<user_id>[^/]+)/$", NotificationConsumer.as_asgi()),
    # Admin dashboard WebSockets
    path("ws/admin/booking-stats/", BookingStatsConsumer.as_asgi()),
    # Notifications WebSocket
    re_path(r"ws/notifications/(?P<user_id>[^/]+)/$", NotificationsConsumer.as_asgi()),
    # Booking status updates WebSocket
    re_path(r"ws/bookings/(?P<shop_id>[^/]+)/$", BookingStatusConsumer.as_asgi()),
    # Analytics WebSocket for shop-specific analytics
    re_path(r"ws/analytics/shop/(?P<shop_id>[^/]+)/$", AnalyticsConsumer.as_asgi()),
    # General analytics WebSocket (platform-wide)
    re_path(r"ws/analytics/(?P<room_name>\w+)/$", AnalyticsConsumer.as_asgi()),
    # Admin dashboard WebSocket for real-time metrics
    re_path(r"ws/admin/dashboard/$", AdminDashboardConsumer.as_asgi()),
    re_path(
        r"ws/admin/system-monitoring/$", consumers.SystemMonitoringConsumer.as_asgi()
    ),
]

# Apply authentication for WebSocket connections
application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
