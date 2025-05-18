from django.urls import path

from apps.notificationsapp.consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/notifications/<str:user_id>/", NotificationConsumer.as_asgi()),
]
