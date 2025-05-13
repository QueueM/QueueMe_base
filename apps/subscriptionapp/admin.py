# apps/subscriptionapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    FeatureUsage,
    Plan,
    PlanFeature,
    Subscription,
    SubscriptionInvoice,
    SubscriptionLog,
)


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 1


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "monthly_price",
        "max_shops",
        "max_services_per_shop",
        "max_specialists_per_shop",
        "is_active",
        "is_featured",
        "position",
    ]
    list_filter = ["is_active", "is_featured"]
    search_fields = ["name", "description"]
    inlines = [PlanFeatureInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "name_ar",
                    "description",
                    "description_ar",
                    "monthly_price",
                )
            },
        ),
        (
            _("Limits"),
            {
                "fields": (
                    "max_shops",
                    "max_services_per_shop",
                    "max_specialists_per_shop",
                )
            },
        ),
        (_("Display"), {"fields": ("is_active", "is_featured", "position")}),
    )


class FeatureUsageInline(admin.TabularInline):
    model = FeatureUsage
    extra = 0
    readonly_fields = ["feature_category", "limit", "current_usage", "last_updated"]
    can_delete = False


class SubscriptionInvoiceInline(admin.TabularInline):
    model = SubscriptionInvoice
    extra = 0
    readonly_fields = [
        "invoice_number",
        "amount",
        "status",
        "period_start",
        "period_end",
        "issued_date",
        "due_date",
        "paid_date",
    ]
    can_delete = False


class SubscriptionLogInline(admin.TabularInline):
    model = SubscriptionLog
    extra = 0
    readonly_fields = [
        "action",
        "status_before",
        "status_after",
        "performed_by",
        "metadata",
        "created_at",
    ]
    can_delete = False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "company",
        "plan",
        "status",
        "period",
        "start_date",
        "end_date",
        "auto_renew",
    ]
    list_filter = ["status", "period", "auto_renew"]
    search_fields = ["company__name", "plan__name", "plan_name"]
    readonly_fields = [
        "moyasar_id",
        "trial_end",
        "current_period_start",
        "current_period_end",
        "created_at",
        "updated_at",
        "canceled_at",
    ]
    raw_id_fields = ["company", "plan"]
    inlines = [FeatureUsageInline, SubscriptionInvoiceInline, SubscriptionLogInline]
    fieldsets = (
        (None, {"fields": ("company", "plan", "status", "period", "auto_renew")}),
        (
            _("Dates"),
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "trial_end",
                    "current_period_start",
                    "current_period_end",
                    "canceled_at",
                )
            },
        ),
        (
            _("Cached Plan Details"),
            {
                "fields": (
                    "plan_name",
                    "max_shops",
                    "max_services_per_shop",
                    "max_specialists_per_shop",
                )
            },
        ),
        (_("Integration"), {"fields": ("moyasar_id",)}),
        (_("Metadata"), {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make company and plan read-only for existing subscriptions
        if obj and obj.pk:
            return self.readonly_fields + ["company", "plan"]
        return self.readonly_fields


@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "subscription",
        "amount",
        "status",
        "issued_date",
        "due_date",
        "paid_date",
    ]
    list_filter = ["status", "issued_date"]
    search_fields = ["invoice_number", "subscription__company__name"]
    readonly_fields = [
        "subscription",
        "invoice_number",
        "amount",
        "status",
        "period_start",
        "period_end",
        "issued_date",
        "due_date",
        "paid_date",
        "transaction",
    ]

    def has_add_permission(self, request):
        # Invoices are created automatically
        return False


@admin.register(FeatureUsage)
class FeatureUsageAdmin(admin.ModelAdmin):
    list_display = [
        "subscription",
        "feature_category",
        "limit",
        "current_usage",
        "last_updated",
    ]
    list_filter = ["feature_category"]
    search_fields = ["subscription__company__name"]
    readonly_fields = ["subscription", "feature_category", "last_updated"]


@admin.register(SubscriptionLog)
class SubscriptionLogAdmin(admin.ModelAdmin):
    list_display = [
        "subscription",
        "action",
        "status_before",
        "status_after",
        "performed_by",
        "created_at",
    ]
    list_filter = ["action", "created_at"]
    search_fields = ["subscription__company__name", "action"]
    readonly_fields = [
        "subscription",
        "action",
        "status_before",
        "status_after",
        "performed_by",
        "metadata",
        "created_at",
    ]

    def has_add_permission(self, request):
        # Logs are created automatically
        return False
