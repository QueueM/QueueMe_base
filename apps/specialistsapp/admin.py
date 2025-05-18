from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.specialistsapp.models import (
    PortfolioItem,
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class SpecialistServiceInline(admin.TabularInline):
    model = SpecialistService
    extra = 1
    fields = (
        "service",
        "is_primary",
        "proficiency_level",
        "custom_duration",
        "booking_count",
    )
    readonly_fields = ("booking_count",)


class SpecialistWorkingHoursInline(admin.TabularInline):
    model = SpecialistWorkingHours
    extra = 1
    fields = ("weekday", "from_hour", "to_hour", "is_off")


class PortfolioItemInline(admin.TabularInline):
    model = PortfolioItem
    extra = 1
    fields = ("title", "image", "description", "service", "category", "is_featured")


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "get_full_name",
        "get_shop_name",
        "experience_years",
        "is_verified",
        "avg_rating",
        "total_bookings",
    )
    list_filter = ("is_verified", "experience_level", "created_at")
    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "employee__shop__name",
    )
    readonly_fields = (
        "avg_rating",
        "total_bookings",
        "created_at",
        "updated_at",
        "verified_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "employee",
                    "bio",
                    "experience_years",
                    "experience_level",
                    "expertise",
                )
            },
        ),
        (_("Verification"), {"fields": ("is_verified", "verified_at")}),
        (_("Statistics"), {"fields": ("avg_rating", "total_bookings")}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    inlines = [
        SpecialistServiceInline,
        SpecialistWorkingHoursInline,
        PortfolioItemInline,
    ]
    filter_horizontal = ("expertise",)

    def get_full_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    get_full_name.short_description = _("Name")

    def get_shop_name(self, obj):
        return obj.employee.shop.name

    get_shop_name.short_description = _("Shop")

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion if specialist has bookings"""
        if obj and obj.total_bookings > 0:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(SpecialistService)
class SpecialistServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "specialist",
        "service",
        "is_primary",
        "proficiency_level",
        "booking_count",
    )
    list_filter = ("is_primary", "proficiency_level")
    search_fields = (
        "specialist__employee__first_name",
        "specialist__employee__last_name",
        "service__name",
    )


@admin.register(SpecialistWorkingHours)
class SpecialistWorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("id", "specialist", "weekday", "from_hour", "to_hour", "is_off")
    list_filter = ("weekday", "is_off")
    search_fields = (
        "specialist__employee__first_name",
        "specialist__employee__last_name",
    )


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "specialist",
        "title",
        "category",
        "service",
        "is_featured",
        "created_at",
    )
    list_filter = ("is_featured", "created_at")
    search_fields = (
        "specialist__employee__first_name",
        "specialist__employee__last_name",
        "title",
    )
    readonly_fields = ("likes_count", "created_at")
