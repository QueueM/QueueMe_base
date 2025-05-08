from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import CityFilter, LocationFilter
from .models import Area, City, Country, Location
from .serializers import (
    AreaSerializer,
    CitySerializer,
    CountrySerializer,
    LocationGeoSerializer,
    LocationSerializer,
    NearbyLocationQuerySerializer,
)
from .services.distance_service import DistanceService
from .services.geo_service import GeoService
from .services.geospatial_query import GeospatialQueryService


class CountryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing countries
    """

    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["name"]
    ordering = ["name"]


class CityViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing cities
    """

    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = CityFilter
    search_fields = ["name"]
    ordering_fields = ["name", "country__name"]
    ordering = ["name"]


class LocationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing locations
    """

    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = LocationFilter
    search_fields = ["address_line1", "postal_code", "place_name"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return GeoJSON serializer if format is geojson"""
        if self.request.query_params.get("format") == "geojson":
            return LocationGeoSerializer
        return LocationSerializer


class AreaViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing areas
    """

    queryset = Area.objects.all()
    serializer_class = AreaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["is_active", "area_type", "city"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "area_type"]
    ordering = ["name"]


class NearbyEntitiesView(APIView):
    """
    API view for finding nearby entities (shops, services, etc.)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_type):
        # Validate parameters
        serializer = NearbyLocationQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract parameters
        validated_data = serializer.validated_data
        latitude = validated_data.get("latitude")
        longitude = validated_data.get("longitude")
        radius = validated_data.get("radius")
        max_results = validated_data.get("max_results")

        # Use the geospatial service to find nearby entities
        try:
            results = GeospatialQueryService.find_nearby_entities(
                latitude=latitude,
                longitude=longitude,
                entity_type=entity_type,
                radius=radius,
                max_results=max_results,
                filters=request.query_params,
            )
            return Response(results)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CheckCityMatchView(APIView):
    """
    API view to check if two locations are in the same city
    Used for shop-customer visibility rules
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        location1_id = request.data.get("location1_id")
        location2_id = request.data.get("location2_id")

        # Alternative: Check with coordinates
        latitude1 = request.data.get("latitude1")
        longitude1 = request.data.get("longitude1")
        latitude2 = request.data.get("latitude2")
        longitude2 = request.data.get("longitude2")

        try:
            if location1_id and location2_id:
                # Check by location IDs
                is_same_city = GeoService.is_same_city_by_locations(
                    location1_id, location2_id
                )
            elif all([latitude1, longitude1, latitude2, longitude2]):
                # Check by coordinates
                is_same_city = GeoService.is_same_city_by_coordinates(
                    float(latitude1),
                    float(longitude1),
                    float(latitude2),
                    float(longitude2),
                )
            else:
                return Response(
                    {"error": "Either location IDs or coordinates pairs are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({"is_same_city": is_same_city})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DistanceMatrixView(APIView):
    """
    API view to calculate distance and travel time between locations
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Origin can be location_id or coordinates
        origin_id = request.data.get("origin_id")
        origin_lat = request.data.get("origin_lat")
        origin_lng = request.data.get("origin_lng")

        # Destinations can be a list of location_ids or coordinates
        destination_ids = request.data.get("destination_ids", [])
        destination_coordinates = request.data.get("destination_coordinates", [])

        # Parameters
        calculate_travel_time = request.data.get("calculate_travel_time", False)

        try:
            if origin_id and destination_ids:
                # Calculate by location IDs
                results = DistanceService.calculate_distance_matrix_by_ids(
                    origin_id, destination_ids, calculate_travel_time
                )
            elif all([origin_lat, origin_lng]) and destination_coordinates:
                # Calculate by coordinates
                results = DistanceService.calculate_distance_matrix_by_coordinates(
                    float(origin_lat),
                    float(origin_lng),
                    destination_coordinates,
                    calculate_travel_time,
                )
            else:
                return Response(
                    {"error": "Invalid parameters provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(results)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GeocodeAddressView(APIView):
    """
    API view to geocode an address to coordinates
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        address = request.data.get("address")
        city = request.data.get("city")
        country = request.data.get("country")

        if not address:
            return Response(
                {"error": "Address is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = GeoService.geocode_address(address, city, country)
            return Response(result)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReverseGeocodeView(APIView):
    """
    API view to reverse geocode coordinates to an address
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        if not latitude or not longitude:
            return Response(
                {"error": "Latitude and longitude are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = GeoService.reverse_geocode(float(latitude), float(longitude))
            return Response(result)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
