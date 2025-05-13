from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.reportanalyticsapp.models import (
    AnalyticsSnapshot,
    AnomalyDetection,
    ReportExecution,
    ScheduledReport,
    ShopAnalytics,
    SpecialistAnalytics,
)
from apps.shopapp.serializers import ShopSerializer
from apps.specialistsapp.serializers import SpecialistSerializer


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
    created_by_details = UserSerializer(source="created_by", read_only=True)
    recipient_user_details = UserSerializer(source="recipient_user", read_only=True)
    parameters = serializers.JSONField(required=False)

    class Meta:
        model = ScheduledReport
        fields = (
            "id",
            "name",
            "report_type",
            "frequency",
            "parameters",
            "recipient_type",
            "recipient_user",
            "recipient_user_details",
            "recipient_shop",
            "recipient_email",
            "next_run",
            "last_run",
            "is_active",
            "created_by",
            "created_by_details",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "last_run")

    def validate(self, data):
        """Validate recipient based on recipient_type"""
        recipient_type = data.get("recipient_type")

        if recipient_type == "user" and not data.get("recipient_user"):
            raise serializers.ValidationError(
                {"recipient_user": "User must be specified for user recipient type"}
            )

        if recipient_type == "shop" and not data.get("recipient_shop"):
            raise serializers.ValidationError(
                {"recipient_shop": "Shop must be specified for shop recipient type"}
            )

        if recipient_type == "email" and not data.get("recipient_email"):
            raise serializers.ValidationError(
                {"recipient_email": "Email must be specified for email recipient type"}
            )

        return data


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
        """Get human-readable entity name"""
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
    """Serializer for dashboard metrics"""

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
    """Serializer for report generation requests"""

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
