from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Service,
    ServiceAftercare,
    ServiceAvailability,
    ServiceException,
    ServiceFAQ,
    ServiceOverview,
    ServiceStep,
)


class ServiceAvailabilityInline(admin.TabularInline):
    model = ServiceAvailability
    extra = 0
    min_num = 0


class ServiceFAQInline(admin.TabularInline):
    model = ServiceFAQ
    extra = 0
    min_num = 0


class ServiceExceptionInline(admin.TabularInline):
    model = ServiceException
    extra = 0
    min_num = 0


class ServiceOverviewInline(admin.TabularInline):
    model = ServiceOverview
    extra = 0
    min_num = 0


class ServiceStepInline(admin.TabularInline):
    model = ServiceStep
    extra = 0
    min_num = 0


class ServiceAftercareInline(admin.TabularInline):
    model = ServiceAftercare
    extra = 0
    min_num = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "category",
        "price",
        "duration",
        "service_location",
        "status",
        "specialists_count",
    )
    list_filter = ("status", "service_location", "is_featured", "shop")
    search_fields = ("name", "description", "shop__name")
    readonly_fields = ("price_halalas", "created_at", "updated_at")
    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "shop",
                    "category",
                    "name",
                    "description",
                    "short_description",
                    "image",
                    "status",
                )
            },
        ),
        (
            _("Pricing & Timing"),
            {
                "fields": (
                    "price",
                    "price_halalas",
                    "duration",
                    "slot_granularity",
                    "buffer_before",
                    "buffer_after",
                )
            },
        ),
        (
            _("Settings"),
            {
                "fields": (
                    "service_location",
                    "has_custom_availability",
                    "min_booking_notice",
                    "max_advance_booking_days",
                    "order",
                    "is_featured",
                )
            },
        ),
        (
            _("System"),
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )
    inlines = [
        ServiceOverviewInline,
        ServiceStepInline,
        ServiceAftercareInline,
        ServiceAvailabilityInline,
        ServiceFAQInline,
        ServiceExceptionInline,
    ]
    save_on_top = True


@admin.register(ServiceFAQ)
class ServiceFAQAdmin(admin.ModelAdmin):
    list_display = ("question", "service", "order")
    list_filter = ("service__shop",)
    search_fields = ("question", "answer", "service__name")


@admin.register(ServiceAvailability)
class ServiceAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("service", "weekday", "from_hour", "to_hour", "is_closed")
    list_filter = ("weekday", "is_closed", "service__shop")
    search_fields = ("service__name",)


@admin.register(ServiceException)
class ServiceExceptionAdmin(admin.ModelAdmin):
    list_display = ("service", "date", "is_closed", "from_hour", "to_hour", "reason")
    list_filter = ("is_closed", "date", "service__shop")
    search_fields = ("service__name", "reason")
    date_hierarchy = "date"
