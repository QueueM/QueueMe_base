from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.shopDashboardApp.views import (
    DashboardDataViewSet,
    DashboardLayoutViewSet,
    DashboardPreferenceViewSet,
    DashboardSettingsViewSet,
    DashboardWidgetViewSet,
    SavedFilterViewSet,
    ScheduledReportViewSet,
)

router = DefaultRouter()
router.register(r"data", DashboardDataViewSet, basename="dashboard-data")
router.register(r"layouts", DashboardLayoutViewSet, basename="dashboard-layouts")
router.register(r"widgets", DashboardWidgetViewSet, basename="dashboard-widgets")
router.register(r"settings", DashboardSettingsViewSet, basename="dashboard-settings")
router.register(r"reports", ScheduledReportViewSet, basename="dashboard-reports")
router.register(r"filters", SavedFilterViewSet, basename="dashboard-filters")
router.register(
    r"preferences", DashboardPreferenceViewSet, basename="dashboard-preferences"
)

urlpatterns = [
    path("", include(router.urls)),
]
