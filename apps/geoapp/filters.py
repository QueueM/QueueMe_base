import django_filters
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from .models import City, Location


class CityFilter(django_filters.FilterSet):
    """Filter for City model"""

    country_name = django_filters.CharFilter(field_name="country__name", lookup_expr="icontains")
    population_gt = django_filters.NumberFilter(field_name="population", lookup_expr="gt")
    population_lt = django_filters.NumberFilter(field_name="population", lookup_expr="lt")

    class Meta:
        model = City
        fields = {
            "name": ["exact", "icontains"],
            "country": ["exact"],
            "is_active": ["exact"],
        }


class LocationFilter(django_filters.FilterSet):
    """Filter for Location model"""

    city_name = django_filters.CharFilter(field_name="city__name", lookup_expr="icontains")
    country_name = django_filters.CharFilter(field_name="country__name", lookup_expr="icontains")
    address = django_filters.CharFilter(field_name="address_line1", lookup_expr="icontains")

    # Distance filter parameters
    lat = django_filters.NumberFilter(method="filter_by_distance", label="Latitude")
    lng = django_filters.NumberFilter(method="filter_by_distance", label="Longitude")
    radius = django_filters.NumberFilter(method="filter_by_distance", label="Radius (km)")

    def filter_by_distance(self, queryset, name, value):
        """Filter locations by distance from point"""
        # We need all three parameters: lat, lng, and radius
        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")
        radius = self.request.query_params.get("radius")

        if lat and lng and radius:
            # Create a point and filter by distance
            point = Point(float(lng), float(lat), srid=4326)
            return (
                queryset.annotate(distance=Distance("coordinates", point))
                .filter(coordinates__distance_lte=(point, D(km=float(radius))))
                .order_by("distance")
            )

        # If parameters are missing, return unmodified queryset
        return queryset

    class Meta:
        model = Location
        fields = {
            "city": ["exact"],
            "country": ["exact"],
            "is_verified": ["exact"],
            "place_type": ["exact", "icontains"],
        }
