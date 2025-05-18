from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.specialistsapp import views

router = DefaultRouter()
router.register(r"", views.SpecialistViewSet, basename="specialist")

urlpatterns = [
    # Shop-specific specialists
    path(
        "shop/<uuid:shop_id>/",
        views.ShopSpecialistsView.as_view(),
        name="shop-specialists",
    ),
    # Service-specific specialists
    path(
        "service/<uuid:service_id>/",
        views.ServiceSpecialistsView.as_view(),
        name="service-specialists",
    ),
    # Top rated specialists
    path(
        "top-rated/",
        views.TopRatedSpecialistsView.as_view(),
        name="top-rated-specialists",
    ),
    # Specialist recommendations for customer
    path(
        "recommendations/",
        views.SpecialistRecommendationsView.as_view(),
        name="specialist-recommendations",
    ),
    # Specialist services
    path(
        "<uuid:specialist_id>/services/",
        views.SpecialistServicesView.as_view(),
        name="specialist-services",
    ),
    path(
        "<uuid:specialist_id>/services/<uuid:pk>/",
        views.SpecialistServiceDetailView.as_view(),
        name="specialist-service-detail",
    ),
    # Specialist working hours
    path(
        "<uuid:specialist_id>/working-hours/",
        views.SpecialistWorkingHoursView.as_view(),
        name="specialist-working-hours",
    ),
    path(
        "<uuid:specialist_id>/working-hours/<uuid:pk>/",
        views.SpecialistWorkingHoursDetailView.as_view(),
        name="specialist-working-hours-detail",
    ),
    # Specialist portfolio
    path(
        "<uuid:specialist_id>/portfolio/",
        views.SpecialistPortfolioView.as_view(),
        name="specialist-portfolio",
    ),
    path(
        "<uuid:specialist_id>/portfolio/<uuid:pk>/",
        views.SpecialistPortfolioItemDetailView.as_view(),
        name="specialist-portfolio-item-detail",
    ),
    # Specialist availability check
    path(
        "<uuid:specialist_id>/availability/<str:date>/",
        views.SpecialistAvailabilityView.as_view(),
        name="specialist-availability",
    ),
    # Specialist verification
    path(
        "<uuid:pk>/verify/",
        views.SpecialistVerificationView.as_view(),
        name="specialist-verify",
    ),
]

urlpatterns += router.urls
