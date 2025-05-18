from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.customersapp.views import CustomerViewSet, FavoritesViewSet, PaymentMethodViewSet

router = DefaultRouter()
router.register(r"profile", CustomerViewSet, basename="customer")
router.register(r"payment-methods", PaymentMethodViewSet, basename="payment-method")
router.register(r"favorites", FavoritesViewSet, basename="favorites")

urlpatterns = [
    path("", include(router.urls)),
]
