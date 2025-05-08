from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notificationsapp.models import DeviceToken, Notification
from apps.notificationsapp.serializers import (
    BulkNotificationSerializer,
    DeviceTokenSerializer,
    MarkNotificationsReadSerializer,
    NotificationListSerializer,
    NotificationSerializer,
)
from apps.notificationsapp.services.notification_service import NotificationService
from apps.rolesapp.decorators import has_permission


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for getting user notifications and marking them as read
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(user=user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        return self.serializer_class

    @action(detail=False, methods=["get"])
    def unread(self):
        """Get unread notifications for the authenticated user"""
        user = self.request.user
        unread_notifications = Notification.objects.filter(
            user=user, status__in=["sent", "delivered"]
        ).order_by("-created_at")

        page = self.paginate_queryset(unread_notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(unread_notifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()

        if notification.status in ["sent", "delivered"]:
            notification.status = "read"
            notification.read_at = timezone.now()
            notification.save()

        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        user = request.user
        unread_count = Notification.objects.filter(
            user=user, status__in=["sent", "delivered"]
        ).update(status="read", read_at=timezone.now())

        return Response(
            {
                "success": True,
                "message": _("Marked {} notifications as read").format(unread_count),
            }
        )

    @action(detail=False, methods=["post"])
    def mark_multiple_read(self, request):
        """Mark multiple notifications as read based on provided IDs"""
        serializer = MarkNotificationsReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_ids = serializer.validated_data["notification_ids"]
        update_count = Notification.objects.filter(
            id__in=notification_ids,
            user=request.user,  # Ensure user can only mark their own notifications
            status__in=["sent", "delivered"],
        ).update(status="read", read_at=timezone.now())

        return Response(
            {
                "success": True,
                "message": _("Marked {} notifications as read").format(update_count),
            }
        )

    @action(detail=False, methods=["get"])
    def count_unread(self, request):
        """Get count of unread notifications"""
        count = Notification.objects.filter(
            user=request.user, status__in=["sent", "delivered"]
        ).count()

        return Response({"unread_count": count})


class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user device tokens for push notifications
    """

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Associate the device token with the authenticated user
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["delete"])
    def delete_by_device_id(self, request):
        """Delete device token by device ID"""
        device_id = request.query_params.get("device_id")

        if not device_id:
            return Response(
                {"error": _("device_id parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_count, _ = DeviceToken.objects.filter(
            user=request.user, device_id=device_id
        ).delete()

        return Response(
            {
                "success": True,
                "message": _("Deleted {} device tokens").format(deleted_count),
            }
        )


class AdminNotificationViewSet(viewsets.GenericViewSet):
    """
    ViewSet for admin users to send notifications
    """

    permission_classes = [permissions.IsAuthenticated]

    @has_permission("notification", "add")
    @action(detail=False, methods=["post"])
    def send_bulk(self, request):
        """Send notifications to multiple users"""
        serializer = BulkNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_type = serializer.validated_data["notification_type"]
        user_ids = serializer.validated_data["user_ids"]
        data = serializer.validated_data.get("data", {})
        scheduled_for = serializer.validated_data.get("scheduled_for")
        channels = serializer.validated_data.get("channels")

        results = []
        for user_id in user_ids:
            notifications = NotificationService.send_notification(
                user_id=user_id,
                notification_type=notification_type,
                data=data,
                scheduled_for=scheduled_for,
                channels=channels,
            )

            # Append notification IDs to results
            for notification in notifications:
                results.append(str(notification.id))

        return Response(
            {
                "success": True,
                "notification_count": len(results),
                "notification_ids": results,
            }
        )
