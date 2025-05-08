from django.contrib import admin

from .models import FraudDetectionRule, PaymentLog, PaymentMethod, Refund, Transaction


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "last_digits", "is_default", "created_at")
    list_filter = ("type", "is_default", "created_at")
    search_fields = ("user__phone_number", "last_digits", "card_brand")
    readonly_fields = ("token", "created_at")
    date_hierarchy = "created_at"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "status", "created_at")
    list_filter = ("status", "transaction_type", "payment_type", "created_at")
    search_fields = ("user__phone_number", "moyasar_id", "description")
    readonly_fields = ("moyasar_id", "metadata", "created_at", "updated_at")
    date_hierarchy = "created_at"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "amount",
                    "payment_type",
                    "status",
                    "transaction_type",
                    "description",
                )
            },
        ),
        ("Related Object", {"fields": ("content_type", "object_id")}),
        ("Payment Details", {"fields": ("payment_method", "moyasar_id", "metadata")}),
        (
            "Failure Information",
            {
                "fields": ("failure_message", "failure_code"),
                "classes": ("collapse",),
            },
        ),
        (
            "Security Information",
            {
                "fields": ("ip_address", "user_agent", "device_fingerprint"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("transaction", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("transaction__moyasar_id", "moyasar_id", "reason")
    readonly_fields = ("moyasar_id", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ("action", "transaction", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("transaction__moyasar_id", "user__phone_number", "details")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(FraudDetectionRule)
class FraudDetectionRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rule_type", "risk_score", "is_active")
    list_filter = ("rule_type", "is_active", "created_at")
    search_fields = ("name", "description")
    fieldsets = (
        (None, {"fields": ("name", "description", "rule_type", "is_active")}),
        ("Risk Assessment", {"fields": ("risk_score", "parameters")}),
    )
