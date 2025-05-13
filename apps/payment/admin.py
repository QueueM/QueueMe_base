from django.contrib import admin

from .models import (
    FraudDetectionRule,
    PaymentLog,
    PaymentMethod,
    PaymentTransaction,
    Refund,
    RefundRequest,
    Transaction,
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "last_digits", "is_default", "created_at")
    list_filter = ("type", "is_default", "created_at")
    search_fields = ("user__phone_number", "last_digits", "card_brand")
    readonly_fields = ("token", "created_at")
    date_hierarchy = "created_at"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amount",
        "status",
        "provider_transaction_id",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "provider_transaction_id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "amount", "currency", "status")}),
        ("User Information", {"fields": ("user",)}),
        (
            "Payment Details",
            {"fields": ("payment_method", "provider_transaction_id", "wallet_type")},
        ),
        (
            "Additional Information",
            {"fields": ("description", "metadata")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amount",
        "status",
        "external_id",
        "created_at",
    )
    list_filter = ("status", "wallet_type", "created_at")
    search_fields = ("id", "external_id", "source_id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "amount", "currency", "status")}),
        ("User/Company Information", {"fields": ("user", "company")}),
        (
            "Payment Details",
            {"fields": ("payment_method", "external_id", "wallet_type", "fees")},
        ),
        (
            "Additional Information",
            {"fields": ("description", "metadata", "source_type", "source_id")},
        ),
        ("Error Information", {"fields": ("error_code", "error_message")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("transaction__provider_transaction_id", "provider_refund_id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("transaction__provider_transaction_id", "provider_refund_id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "action", "details")
    list_filter = ("action", "created_at")
    search_fields = ("action", "details")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(FraudDetectionRule)
class FraudDetectionRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rule_type", "risk_score", "is_active", "created_at")
    list_filter = ("rule_type", "is_active", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
