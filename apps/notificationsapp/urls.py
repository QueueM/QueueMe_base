from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notificationsapp.views import (
    AdminNotificationViewSet,
    DeviceTokenViewSet,
    NotificationViewSet,
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"device-tokens", DeviceTokenViewSet, basename="device-token")
router.register(r"admin", AdminNotificationViewSet, basename="admin-notification")

urlpatterns = [
    path("", include(router.urls)),
]
