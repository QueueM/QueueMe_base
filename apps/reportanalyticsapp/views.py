from datetime import datetime, timedelta

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.reportanalyticsapp.filters import (
    AnomalyDetectionFilter,
    ReportExecutionFilter,
    ScheduledReportFilter,
    ShopAnalyticsFilter,
    SpecialistAnalyticsFilter,
)
from apps.reportanalyticsapp.models import (
    AnomalyDetection,
    ReportExecution,
    ScheduledReport,
    ShopAnalytics,
    SpecialistAnalytics,
)
from apps.reportanalyticsapp.serializers import (
    AnomalyDetectionSerializer,
    DashboardMetricsSerializer,
    ReportExecutionSerializer,
    ReportRequestSerializer,
    ScheduledReportSerializer,
    ShopAnalyticsSerializer,
    SpecialistAnalyticsSerializer,
)
from apps.reportanalyticsapp.services.analytics_service import AnalyticsService
from apps.reportanalyticsapp.services.dashboard_service import DashboardService
from apps.reportanalyticsapp.services.report_service import ReportService
from apps.reportanalyticsapp.tasks import generate_report
from apps.rolesapp.decorators import has_permission, has_shop_permission


class ShopAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """Shop analytics API endpoints"""

    queryset = ShopAnalytics.objects.all()
    serializer_class = ShopAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ShopAnalyticsFilter
    ordering_fields = ["date", "total_bookings", "total_revenue", "customer_ratings"]
    ordering = ["-date"]

    @has_shop_permission("report", "view")
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Queue Me Admin can see all analytics
        if user.user_type == "admin":
            return super().get_queryset()

        # Shop staff can only see their shop analytics
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        shop_ids = PermissionResolver.get_user_shops(user).values_list("id", flat=True)

        return self.queryset.filter(shop_id__in=shop_ids)

    @action(detail=False, methods=["get"])
    def revenue_summary(self, request):
        """Get revenue summary for a shop over time"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response({"error": "shop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        # Default to last 30 days if not specified
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check permissions
        if not request.user.has_perm("shop_analytics.view_revenue"):
            return Response(
                {"error": "You don't have permission to view revenue data"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get revenue data
        revenue_data = AnalyticsService.get_shop_revenue_summary(shop_id, start_date, end_date)

        return Response(revenue_data)

    @action(detail=False, methods=["get"])
    def booking_trends(self, request):
        """Get booking trends for a shop over time"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response({"error": "shop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        # Default to last 30 days if not specified
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get booking trends
        booking_data = AnalyticsService.get_shop_booking_trends(shop_id, start_date, end_date)

        return Response(booking_data)


class SpecialistAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """Specialist analytics API endpoints"""

    queryset = SpecialistAnalytics.objects.all()
    serializer_class = SpecialistAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = SpecialistAnalyticsFilter
    ordering_fields = ["date", "total_bookings", "customer_ratings", "utilization_rate"]
    ordering = ["-date"]

    @has_shop_permission("report", "view")
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Queue Me Admin can see all analytics
        if user.user_type == "admin":
            return super().get_queryset()

        # Shop staff can only see their shop's specialists
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        shop_ids = PermissionResolver.get_user_shops(user).values_list("id", flat=True)

        return self.queryset.filter(specialist__employee__shop_id__in=shop_ids)

    @action(detail=False, methods=["get"])
    def performance_comparison(self, request):
        """Compare performance between specialists"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response({"error": "shop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get specialist IDs (optional)
        specialist_ids = request.query_params.get("specialist_ids")
        specialist_id_list = None
        if specialist_ids:
            specialist_id_list = specialist_ids.split(",")

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        # Default to last 30 days if not specified
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get comparison data
        comparison_data = AnalyticsService.compare_specialists(
            shop_id=shop_id,
            specialist_ids=specialist_id_list,
            start_date=start_date,
            end_date=end_date,
        )

        return Response(comparison_data)


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """Scheduled report API endpoints"""

    queryset = ScheduledReport.objects.all()
    serializer_class = ScheduledReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = ScheduledReportFilter
    ordering_fields = ["name", "report_type", "frequency", "next_run", "created_at"]
    ordering = ["-created_at"]
    search_fields = ["name"]

    @has_permission("report", "view")
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Queue Me Admin can see all reports
        if user.user_type == "admin":
            return super().get_queryset()

        # Users can see reports they created or are the recipient of
        return self.queryset.filter(
            Q(created_by=user)
            | Q(recipient_type="user", recipient_user=user)
            | Q(recipient_type="shop", recipient_shop__in=self.get_user_shops(user))
        )

    def get_user_shops(self, user):
        """Get shops that user has access to"""
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        return PermissionResolver.get_user_shops(user)

    @has_permission("report", "add")
    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @has_permission("report", "edit")
    def perform_update(self, serializer):
        """Check ownership or admin rights"""
        instance = self.get_object()
        if instance.created_by != self.request.user and self.request.user.user_type != "admin":
            self.permission_denied(
                self.request, message="You don't have permission to edit this report"
            )

        serializer.save()

    @action(detail=True, methods=["post"])
    def run_now(self, request, pk=None):
        """Run a scheduled report immediately"""
        report = self.get_object()

        # Create execution record
        execution = ReportService.create_execution_for_report(report, request.user)

        # Start report generation task
        generate_report.delay(str(execution.id))

        serializer = ReportExecutionSerializer(execution)
        return Response(serializer.data)


class ReportExecutionViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Report execution API endpoints"""

    queryset = ReportExecution.objects.all()
    serializer_class = ReportExecutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = ReportExecutionFilter
    ordering_fields = ["name", "report_type", "status", "start_time"]
    ordering = ["-start_time"]
    search_fields = ["name"]

    @has_permission("report", "view")
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Queue Me Admin can see all executions
        if user.user_type == "admin":
            return super().get_queryset()

        # Get shops user has access to
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user_shops = PermissionResolver.get_user_shops(user).values_list("id", flat=True)

        # Users can see executions they created or for their shops
        return self.queryset.filter(
            Q(created_by=user)
            | Q(
                scheduled_report__recipient_type="user",
                scheduled_report__recipient_user=user,
            )
            | Q(
                scheduled_report__recipient_type="shop",
                scheduled_report__recipient_shop__id__in=user_shops,
            )
        )

    @has_permission("report", "add")
    def create(self, request, *args, **kwargs):
        """Create and run a new report execution"""
        serializer = ReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create execution record
        execution = ReportService.create_execution(
            report_type=serializer.validated_data["report_type"],
            name=serializer.validated_data["name"],
            parameters=serializer.validated_data.get("parameters", {}),
            user=request.user,
        )

        # Start report generation task
        generate_report.delay(str(execution.id))

        result_serializer = ReportExecutionSerializer(execution)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Get download URL for report"""
        execution = self.get_object()

        if execution.status != "completed" or not execution.file_url:
            return Response(
                {"error": "Report is not completed or no file is available"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"file_url": execution.file_url})


class AnomalyDetectionViewSet(viewsets.ReadOnlyModelViewSet):
    """Anomaly detection API endpoints"""

    queryset = AnomalyDetection.objects.all()
    serializer_class = AnomalyDetectionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AnomalyDetectionFilter
    ordering_fields = ["detection_date", "severity", "created_at"]
    ordering = ["-detection_date", "-severity"]

    @has_permission("report", "view")
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Queue Me Admin can see all anomalies
        if user.user_type == "admin":
            return super().get_queryset()

        # Get shops user has access to
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user_shops = PermissionResolver.get_user_shops(user)
        shop_ids = [str(shop.id) for shop in user_shops]

        # Filter anomalies related to user's shops
        shop_anomalies = self.queryset.filter(entity_type="shop", entity_id__in=shop_ids)

        # Get specialists in user's shops
        from apps.specialistsapp.models import Specialist

        specialists = Specialist.objects.filter(employee__shop__in=user_shops)
        specialist_ids = [str(specialist.id) for specialist in specialists]

        # Filter anomalies related to specialists in user's shops
        specialist_anomalies = self.queryset.filter(
            entity_type="specialist", entity_id__in=specialist_ids
        )

        # Get services in user's shops
        from apps.serviceapp.models import Service

        services = Service.objects.filter(shop__in=user_shops)
        service_ids = [str(service.id) for service in services]

        # Filter anomalies related to services in user's shops
        service_anomalies = self.queryset.filter(entity_type="service", entity_id__in=service_ids)

        # Combine all relevant anomalies
        return shop_anomalies.union(specialist_anomalies, service_anomalies)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """Acknowledge an anomaly"""
        anomaly = self.get_object()

        if anomaly.is_acknowledged:
            return Response(
                {"error": "Anomaly is already acknowledged"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anomaly.acknowledge(request.user)

        serializer = self.get_serializer(anomaly)
        return Response(serializer.data)


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard API endpoints for analytics dashboards"""

    permission_classes = [IsAuthenticated]

    @has_shop_permission("report", "view")
    @action(detail=False, methods=["get"])
    def shop_metrics(self, request):
        """Get dashboard metrics for a shop"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response({"error": "shop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        period = request.query_params.get("period", "week")  # Default to week

        # Default to last 7/30 days based on period
        end_date = datetime.now().date()
        if period == "month":
            start_date = end_date - timedelta(days=30)
        else:  # week
            start_date = end_date - timedelta(days=7)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get dashboard metrics
        metrics = DashboardService.get_shop_dashboard_metrics(
            shop_id=shop_id, start_date=start_date, end_date=end_date
        )

        serializer = DashboardMetricsSerializer(metrics)
        return Response(serializer.data)

    @has_permission("report", "view")
    @action(detail=False, methods=["get"])
    def specialist_metrics(self, request):
        """Get dashboard metrics for a specialist"""
        specialist_id = request.query_params.get("specialist_id")
        if not specialist_id:
            return Response(
                {"error": "specialist_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        period = request.query_params.get("period", "week")  # Default to week

        # Default to last 7/30 days based on period
        end_date = datetime.now().date()
        if period == "month":
            start_date = end_date - timedelta(days=30)
        else:  # week
            start_date = end_date - timedelta(days=7)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Verify user has permission to view this specialist
        specialist = None
        try:
            from apps.specialistsapp.models import Specialist

            specialist = Specialist.objects.get(id=specialist_id)

            # Check if user has access to this specialist's shop
            if request.user.user_type != "admin":
                from apps.rolesapp.services.permission_resolver import PermissionResolver

                user_shops = PermissionResolver.get_user_shops(request.user)
                if specialist.employee.shop not in user_shops:
                    return Response(
                        {"error": "You don't have permission to view this specialist's data"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        except Specialist.DoesNotExist:
            return Response({"error": "Specialist not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get dashboard metrics
        metrics = DashboardService.get_specialist_dashboard_metrics(
            specialist_id=specialist_id, start_date=start_date, end_date=end_date
        )

        serializer = DashboardMetricsSerializer(metrics)
        return Response(serializer.data)

    @has_permission("report", "view")
    @action(detail=False, methods=["get"])
    def platform_metrics(self, request):
        """Get platform-wide metrics for Queue Me admins"""
        # Ensure user is an admin
        if request.user.user_type != "admin":
            return Response(
                {"error": "Only admins can access platform metrics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get date range parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        period = request.query_params.get("period", "week")  # Default to week

        # Default to last 7/30 days based on period
        end_date = datetime.now().date()
        if period == "month":
            start_date = end_date - timedelta(days=30)
        else:  # week
            start_date = end_date - timedelta(days=7)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format, use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get dashboard metrics
        metrics = DashboardService.get_platform_dashboard_metrics(
            start_date=start_date, end_date=end_date
        )

        serializer = DashboardMetricsSerializer(metrics)
        return Response(serializer.data)
