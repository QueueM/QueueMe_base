from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Follow, FollowEvent, FollowStats


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = (
        "customer_phone",
        "shop_name",
        "created_at",
        "notification_preference",
    )
    list_filter = ("notification_preference", "created_at")
    search_fields = ("customer__phone_number", "shop__name")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")

    def customer_phone(self, obj):
        return obj.customer.phone_number

    customer_phone.short_description = _("Customer")

    def shop_name(self, obj):
        return obj.shop.name

    shop_name.short_description = _("Shop")


@admin.register(FollowStats)
class FollowStatsAdmin(admin.ModelAdmin):
    list_display = (
        "shop",
        "follower_count",
        "weekly_growth",
        "monthly_growth",
        "last_calculated",
    )
    search_fields = ("shop__name",)
    readonly_fields = ("id", "last_calculated")

    def has_add_permission(self, request):
        return False  # Prevent manual creation - should be created by signals


@admin.register(FollowEvent)
class FollowEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "customer_phone", "shop_name", "timestamp", "source")
    list_filter = ("event_type", "timestamp", "source")
    search_fields = ("customer__phone_number", "shop__name")
    date_hierarchy = "timestamp"
    readonly_fields = ("id", "timestamp")

    def customer_phone(self, obj):
        return obj.customer.phone_number

    customer_phone.short_description = _("Customer")

    def shop_name(self, obj):
        return obj.shop.name

    shop_name.short_description = _("Shop")
