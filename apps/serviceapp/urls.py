from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ServiceAftercareViewSet,
    ServiceAvailabilityViewSet,
    ServiceExceptionViewSet,
    ServiceFAQViewSet,
    ServiceOverviewViewSet,
    ServiceStepViewSet,
    ServiceViewSet,
)

router = DefaultRouter()
router.register(r"services", ServiceViewSet, basename="service")
router.register(r"services/(?P<service_id>[^/.]+)/faqs", ServiceFAQViewSet, basename="service-faq")
router.register(
    r"services/(?P<service_id>[^/.]+)/availability",
    ServiceAvailabilityViewSet,
    basename="service-availability",
)
router.register(
    r"services/(?P<service_id>[^/.]+)/exceptions",
    ServiceExceptionViewSet,
    basename="service-exception",
)
router.register(
    r"services/(?P<service_id>[^/.]+)/overviews",
    ServiceOverviewViewSet,
    basename="service-overview",
)
router.register(
    r"services/(?P<service_id>[^/.]+)/steps",
    ServiceStepViewSet,
    basename="service-step",
)
router.register(
    r"services/(?P<service_id>[^/.]+)/aftercare",
    ServiceAftercareViewSet,
    basename="service-aftercare",
)

urlpatterns = [
    path("", include(router.urls)),
]
