from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("countries", views.CountryViewSet)
router.register("cities", views.CityViewSet)
router.register("locations", views.LocationViewSet)
router.register("areas", views.AreaViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "nearby/<str:entity_type>/",
        views.NearbyEntitiesView.as_view(),
        name="nearby-entities",
    ),
    path("check-city-match/", views.CheckCityMatchView.as_view(), name="check-city-match"),
    path("distance-matrix/", views.DistanceMatrixView.as_view(), name="distance-matrix"),
    path("geocode/", views.GeocodeAddressView.as_view(), name="geocode-address"),
    path("reverse-geocode/", views.ReverseGeocodeView.as_view(), name="reverse-geocode"),
]
