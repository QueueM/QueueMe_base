from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.reportanalyticsapp.models import (
    AnalyticsSnapshot,
    AnomalyDetection,
    ReportExecution,
    ScheduledReport as AnalyticsScheduledReport,  # Avoid name conflict
    ShopAnalytics,
    SpecialistAnalytics,
)
from apps.shopapp.serializers import ShopSerializer
from apps.specialistsapp.serializers import SpecialistSerializer
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
    SavedFilter,
    ScheduledReport,
)


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsSnapshot
        fields = (
            "id",
            "snapshot_type",
            "frequency",
            "snapshot_date",
            "start_date",
            "end_date",
            "data",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ShopAnalyticsSerializer(serializers.ModelSerializer):
    shop_details = ShopSerializer(source="shop", read_only=True)

    class Meta:
        model = ShopAnalytics
        fields = (
            "id",
            "shop",
            "shop_details",
            "date",
            "total_bookings",
            "bookings_completed",
            "bookings_cancelled",
            "bookings_no_show",
            "total_revenue",
            "avg_wait_time",
            "peak_hours",
            "customer_ratings",
            "new_customers",
            "returning_customers",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class SpecialistAnalyticsSerializer(serializers.ModelSerializer):
    specialist_details = SpecialistSerializer(source="specialist", read_only=True)

    class Meta:
        model = SpecialistAnalytics
        fields = (
            "id",
            "specialist",
            "specialist_details",
            "date",
            "total_bookings",
            "bookings_completed",
            "bookings_cancelled",
            "bookings_no_show",
            "total_service_time",
            "avg_service_duration",
            "customer_ratings",
            "utilization_rate",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ScheduledReportSerializer(serializers.ModelSerializer):
    shop_details = ShopSerializer(source="shop", read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = ScheduledReport
        ref_name = "ShopDashboardApp_ScheduledReportSerializer"  # <-- FIX!
        fields = [
            "id",
            "shop",
            "shop_details",
            "name",
            "description",
            "frequency",
            "day_of_week",
            "day_of_month",
            "time_of_day",
            "recipients",
            "kpis_included",
            "charts_included",
            "date_range",
            "is_active",
            "created_by",
            "last_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "last_sent_at",
            "created_by",
            "shop_details",
        ]

    def validate(self, data):
        frequency = data.get("frequency")
        day_of_week = data.get("day_of_week")
        day_of_month = data.get("day_of_month")

        if frequency == "weekly" and day_of_week is None:
            raise serializers.ValidationError(_("Weekly reports must specify a day of week (0-6)."))
        if frequency == "monthly" and day_of_month is None:
            raise serializers.ValidationError(_("Monthly reports must specify a day of month (1-31)."))
        if day_of_month is not None and (day_of_month < 1 or day_of_month > 31):
            raise serializers.ValidationError(_("Day of month must be between 1 and 31."))
        if day_of_week is not None and (day_of_week < 0 or day_of_week > 6):
            raise serializers.ValidationError(_("Day of week must be between 0 (Sunday) and 6 (Saturday)."))

        recipients = data.get("recipients", [])
        for recipient in recipients:
            if not isinstance(recipient, dict) or not all(
                k in recipient for k in ["email", "type"]
            ):
                raise serializers.ValidationError(
                    _("Recipients must be a list of objects with email and type.")
                )
            if recipient["type"] not in ["email", "internal"]:
                raise serializers.ValidationError(
                    _('Recipient type must be either "email" or "internal".')
                )
        return data

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class ReportExecutionSerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source="created_by", read_only=True)
    scheduled_report_name = serializers.CharField(source="scheduled_report.name", read_only=True)
    parameters = serializers.JSONField(required=False)
    result_data = serializers.JSONField(read_only=True)
    execution_time_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ReportExecution
        fields = (
            "id",
            "scheduled_report",
            "scheduled_report_name",
            "name",
            "report_type",
            "parameters",
            "status",
            "result_data",
            "file_url",
            "error_message",
            "start_time",
            "end_time",
            "execution_time_seconds",
            "created_by",
            "created_by_details",
        )
        read_only_fields = (
            "id",
            "status",
            "result_data",
            "file_url",
            "error_message",
            "start_time",
            "end_time",
            "execution_time_seconds",
        )

    def get_execution_time_seconds(self, obj):
        return obj.execution_time()


class AnomalyDetectionSerializer(serializers.ModelSerializer):
    acknowledged_by_details = UserSerializer(source="acknowledged_by", read_only=True)
    entity_name = serializers.SerializerMethodField()

    class Meta:
        model = AnomalyDetection
        fields = (
            "id",
            "entity_type",
            "entity_id",
            "entity_name",
            "metric_type",
            "detection_date",
            "expected_value",
            "actual_value",
            "deviation_percentage",
            "severity",
            "description",
            "is_acknowledged",
            "acknowledged_by",
            "acknowledged_by_details",
            "acknowledged_at",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "acknowledged_at")

    def get_entity_name(self, obj):
        entity_type = obj.entity_type
        entity_id = obj.entity_id

        if entity_type == "shop":
            from apps.shopapp.models import Shop
            try:
                shop = Shop.objects.get(id=entity_id)
                return shop.name
            except Shop.DoesNotExist:
                return None
        elif entity_type == "specialist":
            from apps.specialistsapp.models import Specialist
            try:
                specialist = Specialist.objects.get(id=entity_id)
                employee = specialist.employee
                return f"{employee.first_name} {employee.last_name}"
            except Specialist.DoesNotExist:
                return None
        elif entity_type == "service":
            from apps.serviceapp.models import Service
            try:
                service = Service.objects.get(id=entity_id)
                return service.name
            except Service.DoesNotExist:
                return None
        return None


class DashboardMetricsSerializer(serializers.Serializer):
    date_range = serializers.CharField(read_only=True)
    total_bookings = serializers.IntegerField(read_only=True)
    completed_bookings = serializers.IntegerField(read_only=True)
    cancelled_bookings = serializers.IntegerField(read_only=True)
    no_show_bookings = serializers.IntegerField(read_only=True)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    average_wait_time = serializers.FloatField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    new_customers = serializers.IntegerField(read_only=True)
    returning_customers = serializers.IntegerField(read_only=True)
    utilization_rate = serializers.FloatField(read_only=True)
    daily_metrics = serializers.DictField(read_only=True)
    top_services = serializers.ListField(read_only=True)
    top_specialists = serializers.ListField(read_only=True)
    anomalies = serializers.ListField(read_only=True)


class ReportRequestSerializer(serializers.Serializer):
    report_type = serializers.CharField()
    name = serializers.CharField()
    parameters = serializers.JSONField(required=False, default=dict)

    def validate_report_type(self, value):
        valid_types = [choice[0] for choice in ReportExecution.REPORT_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid report type. Must be one of: {', '.join(valid_types)}"
            )
        return value


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            "id",
            "title",
            "widget_type",
            "category",
            "kpi_key",
            "chart_type",
            "data_source",
            "data_granularity",
            "config",
            "position",
            "is_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        widget_type = data.get("widget_type")
        if widget_type == "kpi" and not data.get("kpi_key"):
            raise serializers.ValidationError(_("KPI widgets must have a KPI key."))
        if widget_type == "chart":
            if not data.get("chart_type"):
                raise serializers.ValidationError(_("Chart widgets must have a chart type."))
            if not data.get("data_source"):
                raise serializers.ValidationError(_("Chart widgets must have a data source."))
        position = data.get("position", {})
        required_pos_fields = ["x", "y", "w", "h"]
        if not all(field in position for field in required_pos_fields):
            raise serializers.ValidationError(_("Position must contain x, y, w, and h values."))
        return data


class DashboardLayoutSerializer(serializers.ModelSerializer):
    widgets = DashboardWidgetSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    shop_details = ShopSerializer(source="shop", read_only=True)

    class Meta:
        model = DashboardLayout
        fields = [
            "id",
            "shop",
            "shop_details",
            "name",
            "description",
            "is_default",
            "created_by",
            "widgets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "shop_details",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class DashboardLayoutDetailSerializer(DashboardLayoutSerializer):
    widgets = DashboardWidgetSerializer(many=True)

    class Meta(DashboardLayoutSerializer.Meta):
        pass

    def create(self, validated_data):
        widgets_data = validated_data.pop("widgets", [])
        layout = super().create(validated_data)
        for widget_data in widgets_data:
            DashboardWidget.objects.create(layout=layout, **widget_data)
        return layout

    def update(self, instance, validated_data):
        widgets_data = validated_data.pop("widgets", None)
        layout = super().update(instance, validated_data)
        if widgets_data is not None:
            instance.widgets.all().delete()
            for widget_data in widgets_data:
                DashboardWidget.objects.create(layout=layout, **widget_data)
        return layout


class DashboardSettingsSerializer(serializers.ModelSerializer):
    shop_details = ShopSerializer(source="shop", read_only=True)

    class Meta:
        model = DashboardSettings
        fields = [
            "id",
            "shop",
            "shop_details",
            "default_date_range",
            "auto_refresh_interval",
            "custom_theme",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "shop_details"]


class SavedFilterSerializer(serializers.ModelSerializer):
    shop_details = ShopSerializer(source="shop", read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = SavedFilter
        fields = [
            "id",
            "shop",
            "shop_details",
            "name",
            "filter_config",
            "is_favorite",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "shop_details",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class DashboardPreferenceSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    preferred_layout_details = DashboardLayoutSerializer(source="preferred_layout", read_only=True)

    class Meta:
        model = DashboardPreference
        fields = [
            "id",
            "user",
            "user_details",
            "preferred_layout",
            "preferred_layout_details",
            "favorite_kpis",
            "preferred_date_range",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "user",
            "user_details",
            "preferred_layout_details",
        ]


class KPIDataSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    value = serializers.JSONField()
    comparison_value = serializers.JSONField(required=False)
    change_percentage = serializers.FloatField(required=False)
    trend = serializers.CharField(required=False)
    category = serializers.CharField()
    format = serializers.CharField()


class ChartDataSerializer(serializers.Serializer):
    title = serializers.CharField()
    chart_type = serializers.CharField()
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=serializers.JSONField())
    options = serializers.JSONField(required=False)


class TableDataSerializer(serializers.Serializer):
    title = serializers.CharField()
    columns = serializers.ListField(child=serializers.JSONField())
    rows = serializers.ListField(child=serializers.ListField())
    total_rows = serializers.IntegerField()
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=10)


class DashboardDataSerializer(serializers.Serializer):
    time_period = serializers.CharField()
    date_range = serializers.JSONField()
    kpis = KPIDataSerializer(many=True)
    charts = ChartDataSerializer(many=True, required=False)
    tables = TableDataSerializer(many=True, required=False)
