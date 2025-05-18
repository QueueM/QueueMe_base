from django.contrib import admin

from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
    SavedFilter,
    ScheduledReport,
)


@admin.register(DashboardSettings)
class DashboardSettingsAdmin(admin.ModelAdmin):
    list_display = ("shop", "default_date_range", "auto_refresh_interval", "updated_at")
    search_fields = ("shop__name",)
    list_filter = ("default_date_range",)


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = ("title", "widget_type", "category", "kpi_key", "is_visible")


@admin.register(DashboardLayout)
class DashboardLayoutAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "is_default", "created_by", "created_at")
    search_fields = ("name", "shop__name", "created_by__phone_number")
    list_filter = ("is_default", "created_at")
    inlines = [DashboardWidgetInline]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("title", "layout", "widget_type", "category", "is_visible")
    search_fields = ("title", "layout__name", "layout__shop__name")
    list_filter = ("widget_type", "category", "is_visible")


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "frequency",
        "time_of_day",
        "is_active",
        "last_sent_at",
    )
    search_fields = ("name", "shop__name")
    list_filter = ("frequency", "is_active", "created_at")


@admin.register(SavedFilter)
class SavedFilterAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "is_favorite", "created_by", "created_at")
    search_fields = ("name", "shop__name")
    list_filter = ("is_favorite", "created_at")


@admin.register(DashboardPreference)
class DashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_layout", "preferred_date_range", "updated_at")
    search_fields = ("user__phone_number", "preferred_layout__name")
    list_filter = ("preferred_date_range", "updated_at")
