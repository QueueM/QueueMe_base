from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Package, PackageAvailability, PackageFAQ, PackageService


class PackageServiceInline(admin.TabularInline):
    model = PackageService
    extra = 1
    autocomplete_fields = ["service"]
    fields = ["service", "sequence", "custom_duration", "description"]


class PackageAvailabilityInline(admin.TabularInline):
    model = PackageAvailability
    extra = 1
    fields = ["weekday", "from_hour", "to_hour", "is_closed"]


class PackageFAQInline(admin.TabularInline):
    model = PackageFAQ
    extra = 1
    fields = ["question", "answer", "order"]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "shop",
        "discounted_price",
        "original_price",
        "discount_percentage",
        "total_duration",
        "status",
        "package_location",
    ]
    list_filter = ["status", "package_location", "shop", "primary_category"]
    search_fields = ["name", "description", "shop__name"]
    readonly_fields = ["discount_percentage", "total_duration", "current_purchases"]
    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "shop",
                    "name",
                    "description",
                    "image",
                    "primary_category",
                    "package_location",
                )
            },
        ),
        (
            _("Pricing"),
            {"fields": ("original_price", "discounted_price", "discount_percentage")},
        ),
        (_("Duration"), {"fields": ("total_duration",)}),
        (_("Availability"), {"fields": ("status", "start_date", "end_date")}),
        (_("Limitations"), {"fields": ("max_purchases", "current_purchases")}),
    )
    inlines = [PackageServiceInline, PackageAvailabilityInline, PackageFAQInline]
    autocomplete_fields = ["shop", "primary_category"]
    save_on_top = True


@admin.register(PackageService)
class PackageServiceAdmin(admin.ModelAdmin):
    list_display = ["package", "service", "sequence", "effective_duration"]
    list_filter = ["package__shop", "package"]
    search_fields = ["package__name", "service__name"]
    autocomplete_fields = ["package", "service"]


@admin.register(PackageAvailability)
class PackageAvailabilityAdmin(admin.ModelAdmin):
    list_display = ["package", "weekday", "from_hour", "to_hour", "is_closed"]
    list_filter = ["weekday", "is_closed", "package__shop"]
    search_fields = ["package__name"]
    autocomplete_fields = ["package"]


@admin.register(PackageFAQ)
class PackageFAQAdmin(admin.ModelAdmin):
    list_display = ["package", "question", "order"]
    list_filter = ["package__shop"]
    search_fields = ["question", "answer", "package__name"]
    ordering = ["package", "order"]
    autocomplete_fields = ["package"]
