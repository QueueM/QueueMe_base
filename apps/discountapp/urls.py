# apps/discountapp/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.discountapp.views import (
    CouponViewSet,
    DiscountCalculationViewSet,
    PromotionalCampaignViewSet,
    ServiceDiscountViewSet,
)

router = DefaultRouter()
router.register(r"service-discounts", ServiceDiscountViewSet)
router.register(r"coupons", CouponViewSet)
router.register(r"campaigns", PromotionalCampaignViewSet)
router.register(
    r"calculations", DiscountCalculationViewSet, basename="discount-calculation"
)

urlpatterns = [
    path("", include(router.urls)),
]
