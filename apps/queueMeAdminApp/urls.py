from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminNotificationViewSet,
    AuditLogViewSet,
    DashboardStatsView,
    MaintenanceScheduleViewSet,
    PlatformStatusViewSet,
    SupportMessageViewSet,
    SupportTicketViewSet,
    SystemHealthView,
    SystemOverviewView,
    SystemSettingViewSet,
    VerificationRequestViewSet,
)

router = DefaultRouter()
router.register("settings", SystemSettingViewSet)
router.register("notifications", AdminNotificationViewSet)
router.register("verifications", VerificationRequestViewSet)
router.register("support-tickets", SupportTicketViewSet)
router.register("support-messages", SupportMessageViewSet)
router.register("platform-status", PlatformStatusViewSet)
router.register("maintenance", MaintenanceScheduleViewSet)
router.register("audit-logs", AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("overview/", SystemOverviewView.as_view(), name="system-overview"),
    path("dashboard-stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("health/", SystemHealthView.as_view(), name="system-health"),
]
