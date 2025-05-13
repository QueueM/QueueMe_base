from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class DashboardException(APIException):
    """Base exception for dashboard-related errors"""

    status_code = 400
    default_detail = _("A dashboard error occurred.")
    default_code = "dashboard_error"


class InvalidDateRangeException(DashboardException):
    """Exception for invalid date range selection"""

    status_code = 400
    default_detail = _("Invalid date range provided.")
    default_code = "invalid_date_range"


class InvalidKPIException(DashboardException):
    """Exception for invalid KPI request"""

    status_code = 400
    default_detail = _("Invalid KPI requested.")
    default_code = "invalid_kpi"


class InvalidChartTypeException(DashboardException):
    """Exception for invalid chart type"""

    status_code = 400
    default_detail = _("Invalid chart type requested.")
    default_code = "invalid_chart_type"


class DataAggregationException(DashboardException):
    """Exception for data aggregation errors"""

    status_code = 500
    default_detail = _("Error aggregating dashboard data.")
    default_code = "data_aggregation_error"


class ReportGenerationException(DashboardException):
    """Exception for report generation errors"""

    status_code = 500
    default_detail = _("Error generating dashboard report.")
    default_code = "report_generation_error"


class PermissionDeniedException(DashboardException):
    """Exception for permission issues"""

    status_code = 403
    default_detail = _("You do not have permission to access this dashboard data.")
    default_code = "dashboard_permission_denied"
