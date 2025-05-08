from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.reviewapp.views import (
    PlatformReviewViewSet,
    ReviewMetricViewSet,
    ReviewReportViewSet,
    ServiceReviewViewSet,
    ShopReviewViewSet,
    SpecialistReviewViewSet,
)

router = DefaultRouter()
router.register(r"shop", ShopReviewViewSet)
router.register(r"specialist", SpecialistReviewViewSet)
router.register(r"service", ServiceReviewViewSet)
router.register(r"platform", PlatformReviewViewSet)
router.register(r"reports", ReviewReportViewSet)
router.register(r"metrics", ReviewMetricViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
