from django.contrib import admin

from apps.customersapp.models import (
    Customer,
    CustomerPreference,
    FavoriteService,
    FavoriteShop,
    FavoriteSpecialist,
    SavedPaymentMethod,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "city", "created_at", "updated_at")
    search_fields = ("user__phone_number", "name", "city")
    list_filter = ("city", "created_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomerPreference)
class CustomerPreferenceAdmin(admin.ModelAdmin):
    list_display = ("customer", "language", "notification_enabled", "updated_at")
    list_filter = ("language", "notification_enabled")
    search_fields = ("customer__user__phone_number",)


@admin.register(SavedPaymentMethod)
class SavedPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("customer", "payment_type", "is_default", "created_at")
    list_filter = ("payment_type", "is_default", "created_at")
    search_fields = ("customer__user__phone_number",)
    readonly_fields = ("token", "created_at")


@admin.register(FavoriteShop)
class FavoriteShopAdmin(admin.ModelAdmin):
    list_display = ("customer", "shop", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__user__phone_number", "shop__name")


@admin.register(FavoriteSpecialist)
class FavoriteSpecialistAdmin(admin.ModelAdmin):
    list_display = ("customer", "specialist", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "customer__user__phone_number",
        "specialist__employee__first_name",
        "specialist__employee__last_name",
    )


@admin.register(FavoriteService)
class FavoriteServiceAdmin(admin.ModelAdmin):
    list_display = ("customer", "service", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__user__phone_number", "service__name")
