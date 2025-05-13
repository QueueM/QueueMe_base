# apps/discountapp/admin.py
from django.contrib import admin

from apps.discountapp.models import Coupon, CouponUsage, PromotionalCampaign, ServiceDiscount


class ServiceDiscountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "discount_type",
        "value",
        "start_date",
        "end_date",
        "status",
        "used_count",
    )
    list_filter = ("status", "discount_type", "shop", "start_date", "end_date")
    search_fields = ("name", "description", "shop__name")
    readonly_fields = ("used_count", "status", "created_at", "updated_at")
    filter_horizontal = ("services", "categories")
    fieldsets = (
        (None, {"fields": ("name", "description", "shop")}),
        (
            "Discount Details",
            {
                "fields": (
                    "discount_type",
                    "value",
                    "max_discount_amount",
                    "min_purchase_amount",
                    "priority",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "usage_limit",
                    "used_count",
                    "status",
                    "is_combinable",
                )
            },
        ),
        (
            "Applicability",
            {"fields": ("apply_to_all_services", "services", "categories")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    readonly_fields = ("customer", "used_at", "booking", "amount")
    extra = 0
    can_delete = False


class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "shop",
        "discount_type",
        "value",
        "start_date",
        "end_date",
        "status",
        "used_count",
    )
    list_filter = (
        "status",
        "discount_type",
        "shop",
        "start_date",
        "end_date",
        "is_single_use",
        "requires_authentication",
    )
    search_fields = ("code", "name", "description", "shop__name")
    readonly_fields = ("used_count", "status", "created_at", "updated_at")
    filter_horizontal = ("services", "categories")
    inlines = [CouponUsageInline]
    fieldsets = (
        (None, {"fields": ("code", "name", "description", "shop")}),
        (
            "Discount Details",
            {
                "fields": (
                    "discount_type",
                    "value",
                    "max_discount_amount",
                    "min_purchase_amount",
                    "priority",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "usage_limit",
                    "used_count",
                    "status",
                    "is_combinable",
                )
            },
        ),
        (
            "Coupon Specifics",
            {
                "fields": (
                    "is_single_use",
                    "requires_authentication",
                    "is_referral",
                    "referred_by",
                )
            },
        ),
        (
            "Applicability",
            {"fields": ("apply_to_all_services", "services", "categories")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class PromotionalCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "campaign_type",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("campaign_type", "is_active", "shop", "start_date", "end_date")
    search_fields = ("name", "description", "shop__name")
    filter_horizontal = ("coupons", "service_discounts")
    fieldsets = (
        (
            None,
            {"fields": ("name", "description", "shop", "campaign_type", "is_active")},
        ),
        ("Validity", {"fields": ("start_date", "end_date")}),
        ("Related Discounts", {"fields": ("coupons", "service_discounts")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    readonly_fields = ("created_at", "updated_at")


class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ("coupon", "customer", "used_at", "booking", "amount")
    list_filter = ("used_at", "coupon__shop")
    search_fields = ("coupon__code", "customer__phone_number", "booking__id")
    readonly_fields = ("coupon", "customer", "used_at", "booking", "amount")


admin.site.register(ServiceDiscount, ServiceDiscountAdmin)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(PromotionalCampaign, PromotionalCampaignAdmin)
admin.site.register(CouponUsage, CouponUsageAdmin)
