from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "type",
            "channel",
            "subject",
            "body_en",
            "body_ar",
            "variables",
            "is_active",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "channel",
            "subject",
            "body",
            "status",
            "data",
            "created_at",
            "sent_at",
            "delivered_at",
            "read_at",
        ]
        read_only_fields = ["id", "created_at", "sent_at", "delivered_at", "read_at"]


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification lists"""

    class Meta:
        model = Notification
        fields = ["id", "type", "subject", "status", "created_at", "read_at"]
        read_only_fields = ["id", "created_at", "read_at"]


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "token", "platform", "device_id", "is_active"]
        read_only_fields = ["id"]

    def validate(self, data):
        # Ensure token format is valid for the specified platform
        token = data.get("token")
        platform = data.get("platform")

        if platform == "ios" and len(token) != 64:
            raise serializers.ValidationError(_("iOS device tokens must be 64 characters"))

        if platform == "android" and len(token) < 100:
            raise serializers.ValidationError(
                _("FCM tokens for Android must be at least 100 characters")
            )

        return data


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for sending bulk notifications"""

    notification_type = serializers.CharField(required=True)
    user_ids = serializers.ListField(child=serializers.UUIDField(), required=True)
    data = serializers.JSONField(required=False, default=dict)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=["sms", "push", "email", "in_app"]),
        required=False,
    )


class MarkNotificationsReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""

    notification_ids = serializers.ListField(child=serializers.UUIDField(), required=True)
