from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomerReelViewSet, ReelViewSet

# Create router for shop-centric views
shop_router = DefaultRouter()
shop_router.register(r"reels", ReelViewSet, basename="shop-reels")

# Create router for customer-centric views
customer_router = DefaultRouter()
customer_router.register(r"reels", CustomerReelViewSet, basename="customer-reels")

urlpatterns = [
    # Shop routes - accessed with /api/shops/{shop_id}/reels/
    path("shops/<uuid:shop_id>/", include(shop_router.urls)),
    # Customer routes - accessed with /api/reels/
    path("", include(customer_router.urls)),
]
