from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.shopDashboardApp.constants import TIME_PERIOD_CHOICES, TIME_PERIOD_MONTH
from apps.shopDashboardApp.exceptions import InvalidDateRangeException
from apps.shopDashboardApp.filters import (
    DashboardLayoutFilter,
    DashboardSettingsFilter,
    DashboardWidgetFilter,
    ScheduledReportFilter,
)
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
    SavedFilter,
    ScheduledReport,
)
from apps.shopDashboardApp.permissions import (
    CanManageDashboardSettings,
    CanManageScheduledReports,
    HasShopDashboardPermission,
)
from apps.shopDashboardApp.serializers import (
    ChartDataSerializer,
    DashboardDataSerializer,
    DashboardLayoutDetailSerializer,
    DashboardLayoutSerializer,
    DashboardPreferenceSerializer,
    DashboardSettingsSerializer,
    DashboardWidgetSerializer,
    KPIDataSerializer,
    SavedFilterSerializer,
    ScheduledReportSerializer,
    TableDataSerializer,
)
from apps.shopDashboardApp.services.dashboard_service import DashboardService
from apps.shopDashboardApp.services.kpi_service import KPIService
from apps.shopDashboardApp.services.settings_service import SettingsService
from apps.shopDashboardApp.services.stats_service import StatsService


class DashboardDataViewSet(viewsets.ViewSet):
    """API endpoint for fetching dashboard data"""

    queryset = DashboardSettings.objects.all()
    permission_classes = [IsAuthenticated, HasShopDashboardPermission]

    def list(self, request):
        """Get complete dashboard data"""
        # Get shop from query parameters
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range parameters
        time_period = request.query_params.get("time_period", TIME_PERIOD_MONTH)
        if time_period not in dict(TIME_PERIOD_CHOICES):
            return Response(
                {"detail": _("Invalid time period.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        # Get dashboard service
        dashboard_service = DashboardService()

        try:
            # Calculate date range
            date_range = dashboard_service.calculate_date_range(
                time_period, start_date, end_date
            )

            # Get dashboard data
            dashboard_data = dashboard_service.get_dashboard_data(
                shop_id=shop_id,
                user_id=request.user.id,
                time_period=time_period,
                start_date=date_range["start_date"],
                end_date=date_range["end_date"],
            )

            # Serialize and return data
            serializer = DashboardDataSerializer(dashboard_data)
            return Response(serializer.data)

        except InvalidDateRangeException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def kpis(self, request):
        """Get only KPI data"""
        # Get shop from query parameters
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range parameters
        time_period = request.query_params.get("time_period", TIME_PERIOD_MONTH)
        if time_period not in dict(TIME_PERIOD_CHOICES):
            return Response(
                {"detail": _("Invalid time period.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        # Get specific KPIs if requested
        kpi_keys = request.query_params.get("kpis")
        if kpi_keys:
            kpi_keys = kpi_keys.split(",")

        # Get KPI service
        kpi_service = KPIService()

        try:
            # Calculate date range
            dashboard_service = DashboardService()
            date_range = dashboard_service.calculate_date_range(
                time_period, start_date, end_date
            )

            # Get KPI data
            kpi_data = kpi_service.get_kpis(
                shop_id=shop_id,
                start_date=date_range["start_date"],
                end_date=date_range["end_date"],
                kpi_keys=kpi_keys,
            )

            # Serialize and return data
            serializer = KPIDataSerializer(kpi_data, many=True)
            return Response(serializer.data)

        except InvalidDateRangeException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def charts(self, request):
        """Get chart data"""
        # Get shop from query parameters
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range parameters
        time_period = request.query_params.get("time_period", TIME_PERIOD_MONTH)
        if time_period not in dict(TIME_PERIOD_CHOICES):
            return Response(
                {"detail": _("Invalid time period.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        # Get chart parameters
        chart_type = request.query_params.get("chart_type")
        data_source = request.query_params.get("data_source")

        # Get statistics service
        stats_service = StatsService()

        try:
            # Calculate date range
            dashboard_service = DashboardService()
            date_range = dashboard_service.calculate_date_range(
                time_period, start_date, end_date
            )

            # Get chart data
            chart_data = stats_service.get_chart_data(
                shop_id=shop_id,
                chart_type=chart_type,
                data_source=data_source,
                start_date=date_range["start_date"],
                end_date=date_range["end_date"],
            )

            # Serialize and return data
            serializer = ChartDataSerializer(chart_data)
            return Response(serializer.data)

        except InvalidDateRangeException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def tables(self, request):
        """Get table data"""
        # Get shop from query parameters
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range parameters
        time_period = request.query_params.get("time_period", TIME_PERIOD_MONTH)
        if time_period not in dict(TIME_PERIOD_CHOICES):
            return Response(
                {"detail": _("Invalid time period.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        # Get table parameters
        data_source = request.query_params.get("data_source")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 10))

        # Get statistics service
        stats_service = StatsService()

        try:
            # Calculate date range
            dashboard_service = DashboardService()
            date_range = dashboard_service.calculate_date_range(
                time_period, start_date, end_date
            )

            # Get table data
            table_data = stats_service.get_table_data(
                shop_id=shop_id,
                data_source=data_source,
                start_date=date_range["start_date"],
                end_date=date_range["end_date"],
                page=page,
                page_size=page_size,
            )

            # Serialize and return data
            serializer = TableDataSerializer(table_data)
            return Response(serializer.data)

        except InvalidDateRangeException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardLayoutViewSet(viewsets.ModelViewSet):
    """API endpoint for managing dashboard layouts"""

    queryset = DashboardLayout.objects.all()
    serializer_class = DashboardLayoutSerializer
    permission_classes = [IsAuthenticated, HasShopDashboardPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = DashboardLayoutFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        """Filter layouts by shop ID"""
        queryset = super().get_queryset()
        shop_id = self.request.query_params.get("shop_id")

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        return queryset

    def get_serializer_class(self):
        """Use different serializer for detail views"""
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return DashboardLayoutDetailSerializer
        return DashboardLayoutSerializer

    @action(detail=False, methods=["get"])
    def default(self, request):
        """Get default layout for a shop"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # First try to get user's preferred layout
            try:
                preference = DashboardPreference.objects.get(user=request.user)
                if (
                    preference.preferred_layout
                    and preference.preferred_layout.shop_id == shop_id
                ):
                    serializer = self.get_serializer(preference.preferred_layout)
                    return Response(serializer.data)
            except DashboardPreference.DoesNotExist:
                pass

            # If no preference, get the default layout
            layout = DashboardLayout.objects.get(shop_id=shop_id, is_default=True)
            serializer = self.get_serializer(layout)
            return Response(serializer.data)

        except DashboardLayout.DoesNotExist:
            # Create a default layout if none exists
            settings_service = SettingsService()
            layout = settings_service.create_default_layout(shop_id, request.user)

            serializer = self.get_serializer(layout)
            return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        """Set a layout as default"""
        layout = self.get_object()
        layout.is_default = True
        layout.save()
        serializer = self.get_serializer(layout)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate a layout"""
        layout = self.get_object()

        # Create new layout
        new_layout = DashboardLayout.objects.create(
            shop=layout.shop,
            name=f"{layout.name} (Copy)",
            description=layout.description,
            is_default=False,
            created_by=request.user,
        )

        # Duplicate widgets
        for widget in layout.widgets.all():
            DashboardWidget.objects.create(
                layout=new_layout,
                title=widget.title,
                widget_type=widget.widget_type,
                category=widget.category,
                kpi_key=widget.kpi_key,
                chart_type=widget.chart_type,
                data_source=widget.data_source,
                data_granularity=widget.data_granularity,
                config=widget.config,
                position=widget.position,
                is_visible=widget.is_visible,
            )

        serializer = self.get_serializer(new_layout)
        return Response(serializer.data)


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """API endpoint for managing dashboard widgets"""

    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated, HasShopDashboardPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = DashboardWidgetFilter
    search_fields = ["title"]
    ordering_fields = ["title", "created_at", "position"]

    def get_queryset(self):
        """Filter widgets by layout or shop"""
        queryset = super().get_queryset()
        layout_id = self.request.query_params.get("layout_id")
        shop_id = self.request.query_params.get("shop_id")

        if layout_id:
            queryset = queryset.filter(layout_id=layout_id)

        if shop_id:
            queryset = queryset.filter(layout__shop_id=shop_id)

        return queryset


class DashboardSettingsViewSet(viewsets.ModelViewSet):
    """API endpoint for managing dashboard settings"""

    queryset = DashboardSettings.objects.all()
    serializer_class = DashboardSettingsSerializer
    permission_classes = [IsAuthenticated, CanManageDashboardSettings]
    filter_backends = [DjangoFilterBackend]
    filterset_class = DashboardSettingsFilter

    def get_queryset(self):
        """Filter settings by shop"""
        queryset = super().get_queryset()
        shop_id = self.request.query_params.get("shop_id")

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        return queryset

    @action(detail=False, methods=["get"])
    def for_shop(self, request):
        """Get settings for a specific shop"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            settings = DashboardSettings.objects.get(shop_id=shop_id)
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
        except DashboardSettings.DoesNotExist:
            # Create default settings if none exist
            settings_service = SettingsService()
            settings = settings_service.create_default_settings(shop_id)

            serializer = self.get_serializer(settings)
            return Response(serializer.data)


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """API endpoint for managing scheduled reports"""

    queryset = ScheduledReport.objects.all()
    serializer_class = ScheduledReportSerializer
    permission_classes = [IsAuthenticated, CanManageScheduledReports]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ScheduledReportFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "frequency", "created_at", "last_sent_at"]

    def get_queryset(self):
        """Filter reports by shop"""
        queryset = super().get_queryset()
        shop_id = self.request.query_params.get("shop_id")

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        return queryset

    @action(detail=True, methods=["post"])
    def send_now(self, request, pk=None):
        """Manually send a report"""
        report = self.get_object()

        try:
            # Trigger report generation and sending
            from apps.shopDashboardApp.tasks import generate_and_send_report

            generate_and_send_report.delay(str(report.id))

            return Response({"detail": _("Report generation initiated.")})
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def templates(self, request):
        """Get report templates"""
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get report templates from settings service
        settings_service = SettingsService()
        templates = settings_service.get_report_templates(shop_id)

        return Response(templates)


class SavedFilterViewSet(viewsets.ModelViewSet):
    """API endpoint for managing saved dashboard filters"""

    queryset = SavedFilter.objects.all()
    serializer_class = SavedFilterSerializer
    permission_classes = [IsAuthenticated, HasShopDashboardPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "is_favorite"]

    def get_queryset(self):
        """Filter saved filters by shop"""
        queryset = super().get_queryset()
        shop_id = self.request.query_params.get("shop_id")

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        # Additionally filter by user's favorites if requested
        favorites_only = self.request.query_params.get("favorites_only") == "true"
        if favorites_only:
            queryset = queryset.filter(is_favorite=True)

        return queryset

    @action(detail=True, methods=["post"])
    def toggle_favorite(self, request, pk=None):
        """Toggle favorite status of a filter"""
        saved_filter = self.get_object()
        saved_filter.is_favorite = not saved_filter.is_favorite
        saved_filter.save()

        serializer = self.get_serializer(saved_filter)
        return Response(serializer.data)


class DashboardPreferenceViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """API endpoint for managing user dashboard preferences"""

    queryset = DashboardPreference.objects.all()
    serializer_class = DashboardPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter preferences by user"""
        if self.request.user.is_superuser:
            return DashboardPreference.objects.all()

        return DashboardPreference.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Get current user's dashboard preferences"""
        try:
            preference = DashboardPreference.objects.get(user=request.user)
            serializer = self.get_serializer(preference)
            return Response(serializer.data)
        except DashboardPreference.DoesNotExist:
            # Create default preferences if none exist
            settings_service = SettingsService()
            preference = settings_service.create_default_preferences(request.user.id)

            serializer = self.get_serializer(preference)
            return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def set_preferred_layout(self, request):
        """Set user's preferred dashboard layout"""
        layout_id = request.data.get("layout_id")
        if not layout_id:
            return Response(
                {"detail": _("Layout ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            layout = DashboardLayout.objects.get(id=layout_id)

            # Get or create user preference
            preference, created = DashboardPreference.objects.get_or_create(
                user=request.user, defaults={"preferred_date_range": TIME_PERIOD_MONTH}
            )

            preference.preferred_layout = layout
            preference.save()

            serializer = self.get_serializer(preference)
            return Response(serializer.data)
        except DashboardLayout.DoesNotExist:
            return Response(
                {"detail": _("Layout not found.")}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"])
    def set_favorite_kpis(self, request):
        """Set user's favorite KPIs"""
        favorite_kpis = request.data.get("favorite_kpis")
        if favorite_kpis is None:
            return Response(
                {"detail": _("Favorite KPIs are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create user preference
        preference, created = DashboardPreference.objects.get_or_create(
            user=request.user, defaults={"preferred_date_range": TIME_PERIOD_MONTH}
        )

        preference.favorite_kpis = favorite_kpis
        preference.save()

        serializer = self.get_serializer(preference)
        return Response(serializer.data)
