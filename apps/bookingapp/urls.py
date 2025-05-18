# apps/bookingapp/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.bookingapp.views import AppointmentViewSet, MultiServiceBookingViewSet

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet)
router.register(r"multi-service-bookings", MultiServiceBookingViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
