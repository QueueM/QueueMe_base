"""
Notifications app views for QueueMe platform
Handles endpoints related to user notifications, push devices, and notification delivery
"""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.documentation.api_doc_decorators import document_api_endpoint, document_api_viewset
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


@document_api_viewset(
    summary="Notification",
    description="API endpoints for viewing and managing user notifications",
    tags=["Notifications"],
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for getting user notifications and marking them as read
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @document_api_endpoint(
        summary="List notifications",
        description="Retrieve all notifications for the current user",
        responses={200: "Success - Returns list of notifications"},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        """Get all notifications for the authenticated user"""
        return super().list(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Get notification details",
        description="Retrieve details for a specific notification",
        responses={
            200: "Success - Returns notification details",
            404: "Not Found - Notification not found",
        },
        path_params=[{"name": "pk", "description": "Notification ID", "type": "string"}],
        tags=["Notifications"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Get a specific notification"""
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(user=user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        return self.serializer_class

    @document_api_endpoint(
        summary="Get unread notifications",
        description="Retrieve all unread notifications for the current user",
        responses={200: "Success - Returns list of unread notifications"},
        tags=["Notifications"],
    )
    @action(detail=False, methods=["get"])
    def unread(self, request):
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

    @document_api_endpoint(
        summary="Mark notification as read",
        description="Update a specific notification's status to read",
        responses={
            200: "Success - Notification marked as read",
            404: "Not Found - Notification not found",
        },
        path_params=[{"name": "pk", "description": "Notification ID", "type": "string"}],
        tags=["Notifications"],
    )
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

    @document_api_endpoint(
        summary="Mark all notifications as read",
        description="Update all unread notifications to read status",
        responses={200: "Success - All notifications marked as read"},
        tags=["Notifications"],
    )
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
                "message": "Marked {} notifications as read".format(unread_count),
            }
        )

    @document_api_endpoint(
        summary="Mark multiple notifications as read",
        description="Update status of multiple specific notifications to read",
        responses={
            200: "Success - Specified notifications marked as read",
            400: "Bad Request - Invalid data",
        },
        tags=["Notifications"],
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
                "message": "Marked {} notifications as read".format(update_count),
            }
        )

    @document_api_endpoint(
        summary="Count unread notifications",
        description="Get the count of unread notifications for the current user",
        responses={200: "Success - Returns unread count"},
        tags=["Notifications"],
    )
    @action(detail=False, methods=["get"])
    def count_unread(self, request):
        """Get count of unread notifications"""
        count = Notification.objects.filter(
            user=request.user, status__in=["sent", "delivered"]
        ).count()

        return Response({"unread_count": count})


@document_api_viewset(
    summary="Device Token",
    description="API endpoints for managing device tokens used for push notifications",
    tags=["Notifications", "Devices"],
)
class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user device tokens for push notifications
    """

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    @document_api_endpoint(
        summary="List device tokens",
        description="Retrieve all device tokens for the current user",
        responses={200: "Success - Returns list of device tokens"},
        tags=["Notifications", "Devices"],
    )
    def list(self, request, *args, **kwargs):
        """Get all device tokens for the current user"""
        return super().list(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Create device token",
        description="Register a new device token for push notifications",
        responses={
            201: "Created - Device token registered successfully",
            400: "Bad Request - Invalid data",
        },
        tags=["Notifications", "Devices"],
    )
    def create(self, request, *args, **kwargs):
        """Create a new device token"""
        return super().create(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Get device token",
        description="Retrieve a specific device token",
        responses={
            200: "Success - Returns device token details",
            404: "Not Found - Device token not found",
        },
        path_params=[{"name": "pk", "description": "Device Token ID", "type": "string"}],
        tags=["Notifications", "Devices"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Get a specific device token"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update device token",
        description="Update an existing device token",
        responses={
            200: "Success - Device token updated successfully",
            400: "Bad Request - Invalid data",
            404: "Not Found - Device token not found",
        },
        path_params=[{"name": "pk", "description": "Device Token ID", "type": "string"}],
        tags=["Notifications", "Devices"],
    )
    def update(self, request, *args, **kwargs):
        """Update a device token"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Delete device token",
        description="Delete a specific device token",
        responses={
            204: "No Content - Device token deleted successfully",
            404: "Not Found - Device token not found",
        },
        path_params=[{"name": "pk", "description": "Device Token ID", "type": "string"}],
        tags=["Notifications", "Devices"],
    )
    def destroy(self, request, *args, **kwargs):
        """Delete a device token"""
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Associate the device token with the authenticated user
        serializer.save(user=self.request.user)

    @document_api_endpoint(
        summary="Delete device token by device ID",
        description="Remove device token using the device's unique identifier",
        responses={
            200: "Success - Device token(s) deleted successfully",
            400: "Bad Request - Device ID parameter missing",
        },
        query_params=[
            {
                "name": "device_id",
                "description": "Unique device identifier",
                "required": True,
                "type": "string",
            }
        ],
        tags=["Notifications", "Devices"],
    )
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


@document_api_viewset(
    summary="Admin Notification",
    description="API endpoints for administrators to send notifications to users",
    tags=["Notifications", "Admin"],
)
class AdminNotificationViewSet(viewsets.GenericViewSet):
    """
    ViewSet for admin users to send notifications
    """

    permission_classes = [permissions.IsAuthenticated]

    @document_api_endpoint(
        summary="Send bulk notifications",
        description="Send notifications to multiple users at once",
        responses={
            200: "Success - Notifications sent successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Notifications", "Admin"],
    )
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
