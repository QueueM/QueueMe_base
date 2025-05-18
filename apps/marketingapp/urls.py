"""
URL patterns for Marketing app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdClickView,
    AdConversionView,
    AdPaymentViewSet,
    AdServingView,
    AdvertisementViewSet,
    CampaignViewSet,
    MetadataView,
    ShopAdvertisingOverviewView,
)

# Create a router for ViewSets
router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"advertisements", AdvertisementViewSet, basename="advertisement")
router.register(r"payments", AdPaymentViewSet, basename="payment")

# URL patterns for the marketing app
urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Ad serving endpoints
    path("serve/", AdServingView.as_view(), name="ad-serve"),
    path("click/", AdClickView.as_view(), name="ad-click"),
    path("conversion/", AdConversionView.as_view(), name="ad-conversion"),
    # Shop advertising overview
    path(
        "shops/<uuid:shop_id>/advertising/",
        ShopAdvertisingOverviewView.as_view(),
        name="shop-advertising",
    ),
    # Metadata
    path("metadata/", MetadataView.as_view(), name="ad-metadata"),
]
