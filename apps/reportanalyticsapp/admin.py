from django.contrib import admin

from apps.reportanalyticsapp.models import (
    AnalyticsSnapshot,
    AnomalyDetection,
    ReportExecution,
    ScheduledReport,
    ShopAnalytics,
    SpecialistAnalytics,
)


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "snapshot_type",
        "frequency",
        "snapshot_date",
        "start_date",
        "end_date",
        "created_at",
    )
    list_filter = ("snapshot_type", "frequency", "snapshot_date")
    search_fields = ("snapshot_type", "frequency")
    date_hierarchy = "snapshot_date"
    readonly_fields = ("created_at",)


@admin.register(ShopAnalytics)
class ShopAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "shop",
        "date",
        "total_bookings",
        "bookings_completed",
        "total_revenue",
        "customer_ratings",
    )
    list_filter = ("date", "shop")
    search_fields = ("shop__name",)
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")


@admin.register(SpecialistAnalytics)
class SpecialistAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "get_specialist_name",
        "date",
        "total_bookings",
        "bookings_completed",
        "customer_ratings",
        "utilization_rate",
    )
    list_filter = ("date", "specialist__employee__shop")
    search_fields = (
        "specialist__employee__first_name",
        "specialist__employee__last_name",
    )
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")

    def get_specialist_name(self, obj):
        return f"{obj.specialist.employee.first_name} {obj.specialist.employee.last_name}"

    get_specialist_name.short_description = "Specialist"
    get_specialist_name.admin_order_field = "specialist__employee__first_name"


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "report_type",
        "frequency",
        "next_run",
        "is_active",
        "created_by",
    )
    list_filter = ("report_type", "frequency", "is_active")
    search_fields = ("name", "created_by__phone_number")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "report_type", "frequency", "parameters")}),
        (
            "Recipient",
            {
                "fields": (
                    "recipient_type",
                    "recipient_user",
                    "recipient_shop",
                    "recipient_email",
                )
            },
        ),
        ("Schedule", {"fields": ("next_run", "last_run", "is_active", "created_by")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "report_type",
        "status",
        "start_time",
        "end_time",
        "created_by",
    )
    list_filter = ("report_type", "status", "start_time")
    search_fields = ("name", "created_by__phone_number")
    readonly_fields = ("start_time", "end_time", "execution_time")
    fieldsets = (
        (None, {"fields": ("scheduled_report", "name", "report_type", "parameters")}),
        (
            "Execution",
            {
                "fields": (
                    "status",
                    "start_time",
                    "end_time",
                    "execution_time",
                    "created_by",
                )
            },
        ),
        ("Results", {"fields": ("file_url", "error_message")}),
    )

    def execution_time(self, obj):
        time_secs = obj.execution_time()
        if time_secs is not None:
            return f"{time_secs:.2f} seconds"
        return "N/A"

    execution_time.short_description = "Execution Time"


@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    list_display = (
        "entity_type",
        "metric_type",
        "detection_date",
        "deviation_percentage",
        "severity",
        "is_acknowledged",
    )
    list_filter = (
        "entity_type",
        "metric_type",
        "severity",
        "detection_date",
        "is_acknowledged",
    )
    search_fields = ("description", "entity_id")
    date_hierarchy = "detection_date"
    readonly_fields = ("created_at", "acknowledged_at")
    fieldsets = (
        (
            None,
            {"fields": ("entity_type", "entity_id", "metric_type", "detection_date")},
        ),
        (
            "Values",
            {
                "fields": (
                    "expected_value",
                    "actual_value",
                    "deviation_percentage",
                    "severity",
                )
            },
        ),
        ("Description", {"fields": ("description",)}),
        (
            "Acknowledgment",
            {"fields": ("is_acknowledged", "acknowledged_by", "acknowledged_at")},
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )
    actions = ["mark_acknowledged"]

    def mark_acknowledged(self, request, queryset):
        for anomaly in queryset:
            anomaly.acknowledge(request.user)
        self.message_user(request, f"{queryset.count()} anomalies marked as acknowledged.")

    mark_acknowledged.short_description = "Mark selected anomalies as acknowledged"
