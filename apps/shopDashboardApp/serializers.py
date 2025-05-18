from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.shopapp.serializers import ShopSerializer
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
    SavedFilter,
    ScheduledReport,
)


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """Serializer for dashboard widgets"""

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
        """Validate widget configuration based on widget type"""
        widget_type = data.get("widget_type")

        # KPI widgets must have a category and KPI key
        if widget_type == "kpi" and not data.get("kpi_key"):
            raise serializers.ValidationError(_("KPI widgets must have a KPI key."))

        # Chart widgets must have a chart type and data source
        if widget_type == "chart":
            if not data.get("chart_type"):
                raise serializers.ValidationError(_("Chart widgets must have a chart type."))
            if not data.get("data_source"):
                raise serializers.ValidationError(_("Chart widgets must have a data source."))

        # Validate position is properly formatted
        position = data.get("position", {})
        required_pos_fields = ["x", "y", "w", "h"]

        if not all(field in position for field in required_pos_fields):
            raise serializers.ValidationError(_("Position must contain x, y, w, and h values."))

        return data


class DashboardLayoutSerializer(serializers.ModelSerializer):
    """Serializer for dashboard layouts"""

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
        """Create layout with current user as creator"""
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class DashboardLayoutDetailSerializer(DashboardLayoutSerializer):
    """Extended serializer for dashboard layout details"""

    widgets = DashboardWidgetSerializer(many=True)

    class Meta(DashboardLayoutSerializer.Meta):
        pass

    def create(self, validated_data):
        """Create layout with widgets"""
        widgets_data = validated_data.pop("widgets", [])
        layout = super().create(validated_data)

        # Create widgets
        for widget_data in widgets_data:
            DashboardWidget.objects.create(layout=layout, **widget_data)

        return layout

    def update(self, instance, validated_data):
        """Update layout with widgets"""
        widgets_data = validated_data.pop("widgets", None)
        layout = super().update(instance, validated_data)

        if widgets_data is not None:
            # Replace all widgets
            instance.widgets.all().delete()

            for widget_data in widgets_data:
                DashboardWidget.objects.create(layout=layout, **widget_data)

        return layout


class DashboardSettingsSerializer(serializers.ModelSerializer):
    """Serializer for dashboard settings"""

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


class ScheduledReportSerializer(serializers.ModelSerializer):
    """Serializer for scheduled reports"""

    shop_details = ShopSerializer(source="shop", read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = ScheduledReport
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
        """Validate report configuration based on frequency"""
        frequency = data.get("frequency")
        day_of_week = data.get("day_of_week")
        day_of_month = data.get("day_of_month")

        # Weekly reports need day of week
        if frequency == "weekly" and day_of_week is None:
            raise serializers.ValidationError(_("Weekly reports must specify a day of week (0-6)."))

        # Monthly reports need day of month
        if frequency == "monthly" and day_of_month is None:
            raise serializers.ValidationError(
                _("Monthly reports must specify a day of month (1-31).")
            )

        # Validate day of month is within valid range
        if day_of_month is not None and (day_of_month < 1 or day_of_month > 31):
            raise serializers.ValidationError(_("Day of month must be between 1 and 31."))

        # Validate day of week is within valid range
        if day_of_week is not None and (day_of_week < 0 or day_of_week > 6):
            raise serializers.ValidationError(
                _("Day of week must be between 0 (Sunday) and 6 (Saturday).")
            )

        # Validate recipients format
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
        """Create report with current user as creator"""
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class SavedFilterSerializer(serializers.ModelSerializer):
    """Serializer for saved dashboard filters"""

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
        """Create filter with current user as creator"""
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)


class DashboardPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user dashboard preferences"""

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
    """Serializer for KPI data"""

    key = serializers.CharField()
    name = serializers.CharField()
    value = serializers.JSONField()
    comparison_value = serializers.JSONField(required=False)
    change_percentage = serializers.FloatField(required=False)
    trend = serializers.CharField(required=False)
    category = serializers.CharField()
    format = serializers.CharField()


class ChartDataSerializer(serializers.Serializer):
    """Serializer for chart data"""

    title = serializers.CharField()
    chart_type = serializers.CharField()
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=serializers.JSONField())
    options = serializers.JSONField(required=False)


class TableDataSerializer(serializers.Serializer):
    """Serializer for table data"""

    title = serializers.CharField()
    columns = serializers.ListField(child=serializers.JSONField())
    rows = serializers.ListField(child=serializers.ListField())
    total_rows = serializers.IntegerField()
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=10)


class DashboardDataSerializer(serializers.Serializer):
    """Main serializer for dashboard data"""

    time_period = serializers.CharField()
    date_range = serializers.JSONField()
    kpis = KPIDataSerializer(many=True)
    charts = ChartDataSerializer(many=True, required=False)
    tables = TableDataSerializer(many=True, required=False)
