from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.models import User
from apps.authapp.serializers import UserBasicSerializer
from apps.shopapp.models import Shop
from apps.shopapp.serializers import ShopDetailSerializer

from .models import (
    AdminNotification,
    AuditLog,
    MaintenanceSchedule,
    PlatformStatus,
    SupportMessage,
    SupportTicket,
    SystemSetting,
    VerificationRequest,
)


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = [
            "id",
            "key",
            "value",
            "description",
            "category",
            "is_public",
            "last_updated",
        ]
        read_only_fields = ["id", "last_updated"]

    def validate_key(self, value):
        # Ensure keys follow naming convention
        if not all(c.isalnum() or c == "_" for c in value):
            raise serializers.ValidationError(
                _("Keys can only contain alphanumeric characters and underscores.")
            )
        return value.upper()


class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = ["id", "title", "message", "level", "is_read", "data", "created_at"]
        read_only_fields = ["id", "created_at"]


class AdminNotificationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = ["id", "is_read"]


class VerificationRequestSerializer(serializers.ModelSerializer):
    shop = ShopDetailSerializer(read_only=True)
    shop_id = serializers.UUIDField(write_only=True)
    verified_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = VerificationRequest
        fields = [
            "id",
            "shop",
            "shop_id",
            "status",
            "documents",
            "notes",
            "rejection_reason",
            "submitted_at",
            "verified_by",
            "verified_at",
        ]
        read_only_fields = ["id", "submitted_at", "verified_at"]

    def validate_shop_id(self, value):
        try:
            Shop.objects.get(pk=value)
            return value
        except Shop.DoesNotExist:
            raise serializers.ValidationError(_("Shop with this ID does not exist."))


class VerificationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data["action"] == "reject" and not data.get("rejection_reason"):
            raise serializers.ValidationError(
                _("Rejection reason is required when rejecting a verification request.")
            )
        return data


class SupportTicketSerializer(serializers.ModelSerializer):
    created_by = UserBasicSerializer(read_only=True)
    assigned_to = UserBasicSerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    shop = ShopDetailSerializer(read_only=True)
    shop_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "reference_number",
            "subject",
            "description",
            "status",
            "priority",
            "category",
            "created_by",
            "assigned_to",
            "assigned_to_id",
            "shop",
            "shop_id",
            "attachments",
            "created_at",
            "updated_at",
            "message_count",
        ]
        read_only_fields = ["id", "reference_number", "created_at", "updated_at"]

    def get_message_count(self, obj):
        return obj.messages.count()

    def validate_assigned_to_id(self, value):
        if value:
            try:
                User.objects.get(pk=value)
                return value
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    _("User with this ID does not exist.")
                )
        return value

    def validate_shop_id(self, value):
        if value:
            try:
                Shop.objects.get(pk=value)
                return value
            except Shop.DoesNotExist:
                raise serializers.ValidationError(
                    _("Shop with this ID does not exist.")
                )
        return value


class SupportMessageSerializer(serializers.ModelSerializer):
    sender = UserBasicSerializer(read_only=True)
    sender_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "ticket",
            "sender",
            "sender_id",
            "message",
            "attachments",
            "is_from_admin",
            "is_internal_note",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_sender_id(self, value):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required."))

        # Default to request user if not specified
        if not value:
            return request.user.id

        # Only admins can specify a different sender
        if value != str(request.user.id) and not request.user.is_staff:
            raise serializers.ValidationError(
                _("You cannot specify a different sender.")
            )

        try:
            User.objects.get(pk=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User with this ID does not exist."))


class PlatformStatusSerializer(serializers.ModelSerializer):
    component_display = serializers.CharField(
        source="get_component_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PlatformStatus
        fields = [
            "id",
            "component",
            "component_display",
            "status",
            "status_display",
            "description",
            "last_checked",
            "metrics",
        ]
        read_only_fields = ["id", "last_checked"]


class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    created_by = UserBasicSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = MaintenanceSchedule
        fields = [
            "id",
            "title",
            "description",
            "affected_components",
            "start_time",
            "end_time",
            "status",
            "status_display",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        if "start_time" in data and "end_time" in data:
            if data["start_time"] >= data["end_time"]:
                raise serializers.ValidationError(
                    _("End time must be after start time.")
                )

            # Validate that maintenance is scheduled in the future
            if data["start_time"] < serializers.DateTimeField().now:
                raise serializers.ValidationError(
                    _("Maintenance cannot be scheduled in the past.")
                )

        return data


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserBasicSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "action_display",
            "actor",
            "entity_type",
            "entity_id",
            "details",
            "ip_address",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]


class SystemOverviewSerializer(serializers.Serializer):
    """System-wide statistics overview"""

    total_shops = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_specialists = serializers.IntegerField()
    total_services = serializers.IntegerField()
    pending_verifications = serializers.IntegerField()
    open_support_tickets = serializers.IntegerField()
    system_health = serializers.DictField()
    today_bookings = serializers.IntegerField()
    today_queue_tickets = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
