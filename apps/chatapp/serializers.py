from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.employeeapp.models import Employee

from .models import Conversation, Message, Presence, TypingStatus


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for employee details in messages"""

    user_id = serializers.UUIDField(source="user.id")
    phone_number = serializers.CharField(source="user.phone_number")
    role = serializers.SerializerMethodField()
    avatar = serializers.ImageField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "user_id",
            "phone_number",
            "first_name",
            "last_name",
            "role",
            "avatar",
            "position",
        )

    def get_role(self, obj):
        """Get employee role name"""
        # Get the first role as primary role
        from apps.rolesapp.models import UserRole

        user_role = UserRole.objects.filter(user=obj.user).first()
        if user_role:
            return user_role.role.name
        return None


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""

    sender_type = serializers.SerializerMethodField()
    employee_details = serializers.SerializerMethodField()
    formatted_created_at = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "sender",
            "sender_type",
            "employee",
            "employee_details",
            "content",
            "message_type",
            "media_url",
            "is_read",
            "read_at",
            "created_at",
            "formatted_created_at",
        )
        read_only_fields = ("id", "created_at", "read_at", "formatted_created_at")

    def get_sender_type(self, obj):
        """Determine if sender is customer or employee"""
        if obj.sender == obj.conversation.customer:
            return "customer"
        return "shop"

    def get_employee_details(self, obj):
        """Get employee details if message is from shop"""
        if obj.employee:
            return EmployeeSerializer(obj.employee).data
        return None

    def get_formatted_created_at(self, obj):
        """Format timestamp in AM/PM format"""
        return obj.created_at.strftime("%I:%M %p - %d %b, %Y")


class CreateMessageSerializer(serializers.ModelSerializer):
    """Serializer for creating messages"""

    employee_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Message
        fields = ("conversation", "content", "message_type", "media_url", "employee_id")

    def validate(self, data):
        """Validate message creation data"""
        user = self.context["request"].user
        conversation = data.get("conversation")

        # Check if user can send message in this conversation
        if user.user_type == "customer":
            # Customer can only send to their own conversations
            if conversation.customer != user:
                raise serializers.ValidationError(
                    _("You cannot send messages to this conversation")
                )
        else:
            # Employee must belong to the shop of the conversation
            try:
                employee = Employee.objects.get(user=user)
                if employee.shop != conversation.shop:
                    raise serializers.ValidationError(
                        _("You cannot send messages for another shop")
                    )

                # Set employee reference
                data["employee_id"] = employee.id
            except Employee.DoesNotExist:
                raise serializers.ValidationError(
                    _("You are not registered as an employee")
                )

        # Handle media type validation
        if data.get("message_type") in ["image", "video"] and not data.get("media_url"):
            raise serializers.ValidationError(
                _("Media URL is required for image or video messages")
            )

        return data

    def create(self, validated_data):
        """Create a new message"""
        # Extract employee_id from validated data
        employee_id = validated_data.pop("employee_id", None)
        if employee_id:
            validated_data["employee"] = Employee.objects.get(id=employee_id)

        # Set sender to current user
        validated_data["sender"] = self.context["request"].user

        return super().create(validated_data)


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations"""

    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(
        source="customer.phone_number", read_only=True
    )
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    shop_avatar = serializers.ImageField(source="shop.avatar", read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "customer",
            "customer_phone",
            "shop",
            "shop_name",
            "shop_avatar",
            "created_at",
            "updated_at",
            "is_active",
            "last_message",
            "unread_count",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "last_message",
            "unread_count",
        )

    def get_last_message(self, obj):
        """Get the most recent message in the conversation"""
        last_message = obj.messages.order_by("-created_at").first()
        if last_message:
            return {
                "id": last_message.id,
                "content": (
                    last_message.content
                    if last_message.message_type == "text"
                    else f"New {last_message.message_type}"
                ),
                "message_type": last_message.message_type,
                "sender_type": (
                    "customer" if last_message.sender == obj.customer else "shop"
                ),
                "created_at": last_message.created_at.strftime("%I:%M %p - %d %b, %Y"),
                "is_read": last_message.is_read,
            }
        return None

    def get_unread_count(self, obj):
        """Get count of unread messages for the current user"""
        user = self.context.get("request").user

        # If customer, count unread shop messages
        if user.user_type == "customer":
            return obj.messages.filter(is_read=False).exclude(sender=user).count()

        # If employee, count unread customer messages
        return obj.messages.filter(is_read=False, sender=obj.customer).count()


class CreateConversationSerializer(serializers.ModelSerializer):
    """Serializer for creating new conversations"""

    class Meta:
        model = Conversation
        fields = ("shop",)

    def validate(self, data):
        """Validate conversation creation"""
        user = self.context["request"].user

        # Only customers can create conversations
        if user.user_type != "customer":
            raise serializers.ValidationError(
                _("Only customers can create conversations")
            )

        # Check if conversation already exists
        shop = data.get("shop")
        existing = Conversation.objects.filter(customer=user, shop=shop).first()
        if existing:
            raise serializers.ValidationError(
                _("Conversation with this shop already exists")
            )

        return data

    def create(self, validated_data):
        """Create a new conversation"""
        validated_data["customer"] = self.context["request"].user
        return super().create(validated_data)


class PresenceSerializer(serializers.ModelSerializer):
    """Serializer for user presence information"""

    class Meta:
        model = Presence
        fields = ("id", "user", "conversation", "is_online", "last_seen")
        read_only_fields = ("id", "user", "last_seen")


class TypingStatusSerializer(serializers.ModelSerializer):
    """Serializer for user typing status"""

    class Meta:
        model = TypingStatus
        fields = ("id", "user", "conversation", "is_typing", "updated_at")
        read_only_fields = ("id", "user", "updated_at")
