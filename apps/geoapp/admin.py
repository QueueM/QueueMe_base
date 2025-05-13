from __future__ import annotations

from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin as GISModelAdmin  # robust map widget
from django.utils.translation import gettext_lazy as _  # ✅ fixes the NameError

from .models import Area, City, Country, Location


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(City)
class CityAdmin(GISModelAdmin):
    list_display = ("name", "country", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active", "country")
    raw_id_fields = ("country",)


@admin.register(Location)
class LocationAdmin(GISModelAdmin):
    list_display = ("address_line1", "city", "country", "is_verified")
    search_fields = ("address_line1", "place_name")
    list_filter = ("is_verified", "city", "country")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("city", "country")

    fieldsets = (
        (
            _("Address Information"),
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "city",
                    "country",
                    "postal_code",
                )
            },
        ),
        (
            _("Coordinates"),
            {
                "fields": ("coordinates",),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "place_name",
                    "place_type",
                    "is_verified",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(Area)
class AreaAdmin(GISModelAdmin):
    list_display = ("name", "area_type", "city", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active", "area_type", "city")
    raw_id_fields = ("city",)
