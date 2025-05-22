"""
Geo app views for QueueMe platform
Handles endpoints related to geographic data such as countries, cities, areas, and locations.
Also provides geospatial services like finding nearby entities, distance calculations, and geocoding.
"""

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

    Provides CRUD operations for countries that are used throughout the platform
    for address standardization and location-based filtering.

    Endpoints:
    - GET /api/countries/ - List all countries
    - POST /api/countries/ - Create a new country (admin only)
    - GET /api/countries/{id}/ - Get country details
    - PUT/PATCH /api/countries/{id}/ - Update a country (admin only)
    - DELETE /api/countries/{id}/ - Delete a country (admin only)

    Permissions:
    - Authentication required for all operations

    Filtering:
    - is_active: Filter by active status

    Search fields:
    - name: Country name
    - code: Country code (ISO)

    Ordering:
    - name: Country name (default)
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

    Provides CRUD operations for cities that are used throughout the platform
    for location-based filtering, matching customers with nearby shops, etc.

    Endpoints:
    - GET /api/cities/ - List all cities
    - POST /api/cities/ - Create a new city (admin only)
    - GET /api/cities/{id}/ - Get city details
    - PUT/PATCH /api/cities/{id}/ - Update a city (admin only)
    - DELETE /api/cities/{id}/ - Delete a city (admin only)

    Permissions:
    - Authentication required for all operations

    Filtering:
    - Multiple filters available via CityFilter (country, is_active, etc.)

    Search fields:
    - name: City name

    Ordering:
    - name: City name (default)
    - country__name: Country name
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

    Provides CRUD operations for detailed location records, which can be
    associated with shops, companies, customer addresses, etc.

    Endpoints:
    - GET /api/locations/ - List all locations
    - POST /api/locations/ - Create a new location
    - GET /api/locations/{id}/ - Get location details
    - PUT/PATCH /api/locations/{id}/ - Update a location
    - DELETE /api/locations/{id}/ - Delete a location

    Permissions:
    - Authentication required for all operations

    Filtering:
    - Multiple filters available via LocationFilter (city, country, area, etc.)

    Search fields:
    - address_line1: Street address
    - postal_code: ZIP/Postal code
    - place_name: Named place or building

    Ordering:
    - created_at: Creation date (default, descending)
    - updated_at: Last updated date

    Query parameters:
    - format: Set to 'geojson' to receive response in GeoJSON format
    """

    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = LocationFilter
    search_fields = ["address_line1", "postal_code", "place_name"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """
        Return GeoJSON serializer if format is geojson

        Allows clients to request location data in GeoJSON format, which is
        useful for integration with mapping libraries.

        Returns:
            Serializer class: LocationGeoSerializer for GeoJSON format, otherwise LocationSerializer
        """
        if self.request.query_params.get("format") == "geojson":
            return LocationGeoSerializer
        return LocationSerializer


class AreaViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing areas

    Provides CRUD operations for geographic areas within cities, such as
    neighborhoods, districts, or service zones.

    Endpoints:
    - GET /api/areas/ - List all areas
    - POST /api/areas/ - Create a new area
    - GET /api/areas/{id}/ - Get area details
    - PUT/PATCH /api/areas/{id}/ - Update an area
    - DELETE /api/areas/{id}/ - Delete an area

    Permissions:
    - Authentication required for all operations

    Filtering:
    - is_active: Filter by active status
    - area_type: Filter by area type (neighborhood, district, etc.)
    - city: Filter by city ID

    Search fields:
    - name: Area name
    - description: Area description

    Ordering:
    - name: Area name (default)
    - area_type: Area type
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

    Finds entities of a specified type within a given radius of a location,
    useful for location-based discovery features.

    Endpoint:
    - GET /api/geo/nearby/{entity_type}/ - Find nearby entities

    URL parameters:
        entity_type: Type of entity to search for (shop, service, specialist, etc.)

    Query parameters:
        latitude: Latitude coordinate (required)
        longitude: Longitude coordinate (required)
        radius: Search radius in kilometers (default: 5)
        max_results: Maximum number of results to return (default: 20)
        Additional filters specific to the entity type

    Permissions:
    - Authentication required

    Returns:
        Response: List of nearby entities with distance information
            [
                {
                    "id": "uuid",
                    "name": "Entity name",
                    "distance": float,
                    "distance_unit": "km",
                    ...entity-specific fields
                },
                ...
            ]
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_type):
        """
        Handle GET request to find nearby entities

        Validates the request parameters and uses the GeospatialQueryService
        to find entities of the specified type near the given coordinates.

        Args:
            request: The HTTP request
            entity_type: Type of entity to search for

        Returns:
            Response: List of nearby entities

        Status codes:
            200: Search successful
            400: Invalid parameters
        """
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

    Determines whether two locations (specified either by location IDs or
    coordinates) are in the same city. Used for shop-customer visibility rules.

    Endpoint:
    - POST /api/geo/check-city-match/ - Check if locations are in the same city

    Request body:
        Either:
            location1_id: UUID of first location
            location2_id: UUID of second location
        Or:
            latitude1: Latitude of first location
            longitude1: Longitude of first location
            latitude2: Latitude of second location
            longitude2: Longitude of second location

    Permissions:
    - Authentication required

    Returns:
        Response: City match result
            {
                "is_same_city": boolean
            }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Handle POST request to check city match

        Checks whether two locations are in the same city, using either
        location IDs or coordinates.

        Args:
            request: The HTTP request

        Returns:
            Response: City match result

        Status codes:
            200: Check successful
            400: Invalid parameters
        """
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

    Calculates the distance and optionally travel time between an origin point
    and one or more destination points. Used for routing, delivery estimation, etc.

    Endpoint:
    - POST /api/geo/distance-matrix/ - Calculate distances between locations

    Request body:
        Either:
            origin_id: UUID of origin location
            destination_ids: List of UUIDs for destination locations
        Or:
            origin_lat: Latitude of origin point
            origin_lng: Longitude of origin point
            destination_coordinates: List of [lat, lng] coordinate pairs

        Optional:
            calculate_travel_time: Boolean, whether to include travel time (default: false)

    Permissions:
    - Authentication required

    Returns:
        Response: Distance matrix results
            {
                "distances": [
                    {
                        "destination_id": "uuid" or "index_0",
                        "distance": float,
                        "distance_unit": "km",
                        "travel_time": integer (seconds, optional),
                        "travel_time_text": "X mins" (optional)
                    },
                    ...
                ]
            }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Handle POST request to calculate distance matrix

        Calculates distances between an origin point and multiple destination
        points, using either location IDs or coordinates.

        Args:
            request: The HTTP request

        Returns:
            Response: Distance matrix results

        Status codes:
            200: Calculation successful
            400: Invalid parameters
        """
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

    Converts a text address into geographic coordinates (latitude/longitude).
    Used for address validation and location-based features.

    Endpoint:
    - POST /api/geo/geocode/ - Geocode an address

    Request body:
        address: Address text to geocode (required)
        city: City name (optional, improves accuracy)
        country: Country name (optional, improves accuracy)

    Permissions:
    - Authentication required

    Returns:
        Response: Geocoding results
            {
                "latitude": float,
                "longitude": float,
                "formatted_address": "Complete address",
                "city": "City name",
                "country": "Country name",
                "postal_code": "Postal code",
                ...additional address components
            }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Handle POST request to geocode an address

        Converts a text address into geographic coordinates using
        the GeoService.

        Args:
            request: The HTTP request

        Returns:
            Response: Geocoding results

        Status codes:
            200: Geocoding successful
            400: Invalid address or geocoding error
        """
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

    Converts geographic coordinates (latitude/longitude) into a text address.
    Used for displaying addresses from location selection on maps.

    Endpoint:
    - POST /api/geo/reverse-geocode/ - Reverse geocode coordinates

    Request body:
        latitude: Latitude coordinate (required)
        longitude: Longitude coordinate (required)

    Permissions:
    - Authentication required

    Returns:
        Response: Reverse geocoding results
            {
                "formatted_address": "Complete address",
                "address_components": {
                    "street_number": "123",
                    "street": "Main St",
                    "city": "City name",
                    "state": "State name",
                    "country": "Country name",
                    "postal_code": "Postal code"
                }
            }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Handle POST request to reverse geocode coordinates

        Converts geographic coordinates into a text address using
        the GeoService.

        Args:
            request: The HTTP request

        Returns:
            Response: Reverse geocoding results

        Status codes:
            200: Reverse geocoding successful
            400: Missing coordinates or geocoding error
        """
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
