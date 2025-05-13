from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.notificationsapp.models import (
    DeviceToken,
    Notification,
    NotificationDelivery,
    NotificationTemplate,
    UserNotificationSettings,
)


class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("type", "channel", "is_active")
    list_filter = ("type", "channel", "is_active")
    search_fields = ("type", "subject", "body_en", "body_ar")
    fieldsets = (
        (None, {"fields": ("type", "channel", "is_active")}),
        (_("Content"), {"fields": ("subject", "body_en", "body_ar", "variables")}),
    )


class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "title", "created_at", "updated_at")
    list_filter = ("notification_type", "priority", "cancelled")
    search_fields = ("title", "message", "notification_type")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("notification_type", "template", "priority", "cancelled")}),
        (_("Content"), {"fields": ("title", "message", "data")}),
        (_("Timing"), {"fields": ("created_at", "updated_at")}),
    )


class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "user_id", "channel", "status", "scheduled_time")
    list_filter = ("status", "channel")
    search_fields = ("user_id", "error_message")
    readonly_fields = ("created_at", "updated_at", "delivered_at", "read_at")
    fieldsets = (
        (None, {"fields": ("notification", "user_id", "channel", "status")}),
        (_("Details"), {"fields": ("error_message", "attempts")}),
        (
            _("Timing"),
            {
                "fields": (
                    "scheduled_time",
                    "delivered_at",
                    "read_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "last_used_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__phone_number", "device_id")
    readonly_fields = ("created_at", "last_used_at")


class UserNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user_id",
        "email_enabled",
        "push_enabled",
        "sms_enabled",
        "in_app_enabled",
    )
    list_filter = ("email_enabled", "push_enabled", "sms_enabled", "in_app_enabled")
    search_fields = ("user_id",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("user_id",)}),
        (
            _("Channels"),
            {
                "fields": (
                    "email_enabled",
                    "push_enabled",
                    "sms_enabled",
                    "in_app_enabled",
                )
            },
        ),
        (_("Preferences"), {"fields": ("preferences",)}),
        (_("Timing"), {"fields": ("created_at", "updated_at")}),
    )


admin.site.register(NotificationTemplate, NotificationTemplateAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(NotificationDelivery, NotificationDeliveryAdmin)
admin.site.register(DeviceToken, DeviceTokenAdmin)
admin.site.register(UserNotificationSettings, UserNotificationSettingsAdmin)
