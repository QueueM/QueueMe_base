from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate


class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("type", "channel", "is_active")
    list_filter = ("type", "channel", "is_active")
    search_fields = ("type", "subject", "body_en", "body_ar")
    fieldsets = (
        (None, {"fields": ("type", "channel", "is_active")}),
        (_("Content"), {"fields": ("subject", "body_en", "body_ar", "variables")}),
    )


class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "channel", "status", "created_at")
    list_filter = ("status", "type", "channel")
    search_fields = ("user__phone_number", "subject", "body")
    readonly_fields = ("created_at", "sent_at", "delivered_at", "read_at")
    fieldsets = (
        (None, {"fields": ("user", "template", "type", "channel", "status")}),
        (_("Content"), {"fields": ("subject", "body", "data")}),
        (
            _("Timing"),
            {
                "fields": (
                    "scheduled_for",
                    "created_at",
                    "sent_at",
                    "delivered_at",
                    "read_at",
                )
            },
        ),
    )


class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "last_used_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__phone_number", "device_id")
    readonly_fields = ("created_at", "last_used_at")


admin.site.register(NotificationTemplate, NotificationTemplateAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(DeviceToken, DeviceTokenAdmin)
