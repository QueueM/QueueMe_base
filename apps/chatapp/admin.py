from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Conversation, Message, Presence, TypingStatus


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = (
        "sender",
        "employee",
        "content",
        "message_type",
        "media_url",
        "is_read",
        "read_at",
        "created_at",
    )
    can_delete = False
    max_num = 20

    def has_add_permission(self, request, obj):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_info",
        "shop_name",
        "message_count",
        "created_at",
        "updated_at",
        "is_active",
    )
    list_filter = ("is_active", "shop")
    search_fields = ("customer__phone_number", "shop__name")
    date_hierarchy = "created_at"
    inlines = [MessageInline]
    readonly_fields = ("created_at", "updated_at")

    def customer_info(self, obj):
        return f"{obj.customer.phone_number}"

    customer_info.short_description = _("Customer")

    def shop_name(self, obj):
        return obj.shop.name

    shop_name.short_description = _("Shop")

    def message_count(self, obj):
        return obj.messages.count()

    message_count.short_description = _("Messages")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation_info",
        "sender_type",
        "message_preview",
        "message_type",
        "has_media",
        "is_read",
        "created_at",
    )
    list_filter = ("message_type", "is_read", "created_at")
    search_fields = ("content", "sender__phone_number", "conversation__shop__name")
    readonly_fields = ("created_at", "read_at")
    date_hierarchy = "created_at"

    def conversation_info(self, obj):
        return f"{obj.conversation.customer.phone_number} - {obj.conversation.shop.name}"

    conversation_info.short_description = _("Conversation")

    def sender_type(self, obj):
        if obj.employee:
            return f"Employee: {obj.employee.first_name}"
        else:
            return f"Customer: {obj.sender.phone_number}"

    sender_type.short_description = _("Sender")

    def message_preview(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content

    message_preview.short_description = _("Message")

    def has_media(self, obj):
        return bool(obj.media_url)

    has_media.boolean = True
    has_media.short_description = _("Has Media")


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user_info", "conversation_info", "is_online", "last_seen")
    list_filter = ("is_online",)

    def user_info(self, obj):
        return obj.user.phone_number

    user_info.short_description = _("User")

    def conversation_info(self, obj):
        return f"{obj.conversation.customer.phone_number} - {obj.conversation.shop.name}"

    conversation_info.short_description = _("Conversation")


@admin.register(TypingStatus)
class TypingStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "user_info", "conversation_info", "is_typing", "updated_at")
    list_filter = ("is_typing",)

    def user_info(self, obj):
        return obj.user.phone_number

    user_info.short_description = _("User")

    def conversation_info(self, obj):
        return f"{obj.conversation.customer.phone_number} - {obj.conversation.shop.name}"

    conversation_info.short_description = _("Conversation")
