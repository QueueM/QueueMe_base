"""
Admin configuration for Marketing app models.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AdClick, AdPayment, Advertisement, AdView, Campaign


class AdvertisementInline(admin.TabularInline):
    model = Advertisement
    extra = 0
    readonly_fields = ["impression_count", "click_count", "conversion_count"]
    fields = [
        "title",
        "ad_type",
        "status",
        "impression_count",
        "click_count",
        "conversion_count",
    ]
    show_change_link = True


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "company",
        "shop",
        "start_date",
        "end_date",
        "budget",
        "budget_spent",
        "is_active",
        "ad_count",
    ]
    list_filter = ["is_active", "company", "shop", "start_date"]
    search_fields = ["name", "company__name", "shop__name"]
    readonly_fields = ["budget_spent"]
    inlines = [AdvertisementInline]

    def ad_count(self, obj):
        return obj.advertisements.count()

    ad_count.short_description = "Ads"


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "campaign",
        "shop_name",
        "ad_type",
        "targeting_type",
        "status",
        "display_preview",
        "impression_count",
        "click_count",
        "click_through_rate_display",
    ]
    list_filter = ["status", "ad_type", "targeting_type", "created_at"]
    search_fields = ["title", "campaign__name", "description"]
    readonly_fields = [
        "impression_count",
        "click_count",
        "conversion_count",
        "click_through_rate",
        "cost_per_conversion",
    ]

    fieldsets = (
        (None, {"fields": ("title", "description", "campaign")}),
        ("Content", {"fields": ("ad_type", "image", "video")}),
        (
            "Targeting",
            {"fields": ("targeting_type", "target_cities", "target_categories")},
        ),
        ("Linked Content", {"fields": ("content_type", "object_id")}),
        ("Pricing", {"fields": ("cost_per_view", "cost_per_click", "amount")}),
        ("Status", {"fields": ("status", "payment_date")}),
        (
            "Metrics",
            {
                "fields": (
                    "impression_count",
                    "click_count",
                    "conversion_count",
                    "click_through_rate",
                    "cost_per_conversion",
                )
            },
        ),
    )

    def shop_name(self, obj):
        if obj.campaign and obj.campaign.shop:
            return obj.campaign.shop.name
        return "-"

    shop_name.short_description = "Shop"

    def display_preview(self, obj):
        if obj.ad_type == "image" and obj.image:
            return format_html('<img src="{}" height="50" />', obj.image.url)
        elif obj.ad_type == "video" and obj.video:
            return format_html(
                '<video width="100" height="50" controls><source src="{}"></video>',
                obj.video.url,
            )
        return "No preview"

    display_preview.short_description = "Preview"

    def click_through_rate_display(self, obj):
        return f"{obj.click_through_rate:.2f}%"

    click_through_rate_display.short_description = "CTR"


@admin.register(AdView)
class AdViewAdmin(admin.ModelAdmin):
    list_display = [
        "ad",
        "user",
        "viewed_at",
        "ip_address",
    ]
    list_filter = ["viewed_at", "user"]
    search_fields = ["ad__title", "user__email", "ip_address"]
    date_hierarchy = "viewed_at"
    readonly_fields = [
        "ad",
        "user",
        "ip_address",
        "user_agent",
        "viewed_at",
        "location",
    ]


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ["ad", "user", "clicked_at", "led_to_booking", "ip_address"]
    list_filter = ["clicked_at", "led_to_booking", "user"]
    search_fields = ["ad__title", "user__email", "ip_address"]
    date_hierarchy = "clicked_at"
    readonly_fields = [
        "ad",
        "user",
        "ip_address",
        "user_agent",
        "clicked_at",
        "referrer",
        "led_to_booking",
        "conversion_value",
        "location",
    ]


@admin.register(AdPayment)
class AdPaymentAdmin(admin.ModelAdmin):
    list_display = [
        "advertisement",
        "amount",
        "payment_date",
        "status",
        "payment_method",
    ]
    list_filter = ["status", "payment_date", "payment_method"]
    search_fields = ["advertisement__title", "transaction_id", "invoice_number"]
    readonly_fields = [
        "advertisement",
        "amount",
        "transaction_id",
        "payment_method",
        "payment_date",
        "status",
        "invoice_number",
    ]
