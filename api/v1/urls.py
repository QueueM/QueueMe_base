# api/v1/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.documentation.swagger import schema_view
from api.v1.views.index import api_root
from api.v1.views.service_availability_views import (
    BestSpecialistAPIView,
    DynamicServiceAvailabilityAPIView,
    PopularTimeSlotsAPIView,
    QuietTimeSlotsAPIView,
    ServiceAvailabilityAPIView,
)
from apps.authapp.views import AuthViewSet
from apps.bookingapp.views import AppointmentViewSet
from apps.categoriesapp.views import CategoryViewSet
from apps.chatapp.views import ConversationViewSet, MessageViewSet
from apps.companiesapp.views import CompanyViewSet
from apps.customersapp.views import CustomerViewSet
from apps.employeeapp.views import EmployeeViewSet
from apps.followapp.views import FollowViewSet
from apps.notificationsapp.views import NotificationViewSet
from apps.payment.views import PaymentViewSet
from apps.queueapp.views import QueueTicketViewSet, QueueViewSet
from apps.reelsapp.views import ReelViewSet
from apps.reviewapp.views import ReviewViewSet
from apps.serviceapp.views import ServiceViewSet
from apps.shopapp.views import ShopViewSet
from apps.specialistsapp.views import SpecialistViewSet
from apps.storiesapp.views import StoryViewSet

# Create a router for v1 API endpoints
router = DefaultRouter()

# Import app-specific viewsets and register them

# Register routes
router.register(r"auth", AuthViewSet, basename="auth")
router.register(r"shops", ShopViewSet, basename="shop")
router.register(r"services", ServiceViewSet, basename="service")
router.register(r"specialists", SpecialistViewSet, basename="specialist")
router.register(r"appointments", AppointmentViewSet, basename="appointment")
router.register(r"queues", QueueViewSet, basename="queue")
router.register(r"queue-tickets", QueueTicketViewSet, basename="queue-ticket")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"conversations", ConversationViewSet, basename="conversation")
router.register(r"messages", MessageViewSet, basename="message")
router.register(r"reels", ReelViewSet, basename="reel")
router.register(r"stories", StoryViewSet, basename="story")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"follows", FollowViewSet, basename="follow")

# API URLs
urlpatterns = [
    # API root view
    path("", api_root, name="api-root"),
    # Include router URLs
    path("", include(router.urls)),
    # Include app-specific URLs
    path("auth/", include("apps.authapp.urls")),
    path("bookings/", include("apps.bookingapp.urls")),
    path("shops/", include("apps.shopapp.urls")),
    path("services/", include("apps.serviceapp.urls")),
    path("queue/", include("apps.queueapp.urls", namespace="api_queueapp")),
    path("chat/", include("apps.chatapp.urls")),
    path("geo/", include("apps.geoapp.urls")),
    path("payments/", include("apps.payment.urls")),
    path("subscriptions/", include("apps.subscriptionapp.urls")),
    path("dashboard/", include("apps.shopDashboardApp.urls")),
    path("analytics/", include("apps.reportanalyticsapp.urls")),
    # path("verifications/", include("apps.shopapp.verification_urls")),  # Commented out due to missing module
    path("roles/", include("apps.rolesapp.urls", namespace="api_rolesapp")),
    # Availability endpoints
    path(
        "availability/service/",
        ServiceAvailabilityAPIView.as_view(),
        name="service-availability",
    ),
    path(
        "availability/dynamic/",
        DynamicServiceAvailabilityAPIView.as_view(),
        name="dynamic-availability",
    ),
    path(
        "availability/popular-slots/",
        PopularTimeSlotsAPIView.as_view(),
        name="popular-slots",
    ),
    path("availability/quiet-slots/", QuietTimeSlotsAPIView.as_view(), name="quiet-slots"),
    path(
        "availability/best-specialist/",
        BestSpecialistAPIView.as_view(),
        name="best-specialist",
    ),
    # API documentation
    path(
        "docs/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "docs/redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
]
