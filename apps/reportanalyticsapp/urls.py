from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.reportanalyticsapp.views import (
    AnomalyDetectionViewSet,
    DashboardViewSet,
    ReportExecutionViewSet,
    ScheduledReportViewSet,
    ShopAnalyticsViewSet,
    SpecialistAnalyticsViewSet,
)

router = DefaultRouter()
router.register(r"shop-analytics", ShopAnalyticsViewSet)
router.register(r"specialist-analytics", SpecialistAnalyticsViewSet)
router.register(r"scheduled-reports", ScheduledReportViewSet)
router.register(r"report-executions", ReportExecutionViewSet)
router.register(r"anomalies", AnomalyDetectionViewSet)
router.register(r"dashboard", DashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]
