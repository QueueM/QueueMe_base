import logging

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q

from ..models import City, Country, Location

logger = logging.getLogger(__name__)


class GeoService:
    """Main geolocation service with various utility functions"""

    @staticmethod
    def is_same_city_by_locations(location1_id, location2_id):
        """Check if two locations are in the same city"""
        try:
            location1 = Location.objects.get(id=location1_id)
            location2 = Location.objects.get(id=location2_id)

            # Check if they have the same city
            return location1.city_id == location2.city_id
        except Location.DoesNotExist:
            logger.error(f"Location not found: {location1_id} or {location2_id}")
            return False
        except Exception as e:
            logger.error(f"Error checking city match: {str(e)}")
            return False

    @staticmethod
    def is_same_city_by_coordinates(lat1, lng1, lat2, lng2):
        """Check if coordinates are in the same city using reverse geocoding"""
        try:
            # Create points
            point1 = Point(float(lng1), float(lat1), srid=4326)
            point2 = Point(float(lng2), float(lat2), srid=4326)

            # Find cities for these points
            city1 = (
                City.objects.annotate(distance=Distance("location", point1))
                .order_by("distance")
                .first()
            )

            city2 = (
                City.objects.annotate(distance=Distance("location", point2))
                .order_by("distance")
                .first()
            )

            if city1 and city2:
                return city1.id == city2.id

            # Fallback: Check if within same area
            # If cities are not found, check if points are close to each other (within 5km)
            from .distance_service import DistanceService

            distance_km = DistanceService.calculate_haversine_distance(lat1, lng1, lat2, lng2)

            # If very close (within 5km), assume same city
            return distance_km < 5
        except Exception as e:
            logger.error(f"Error checking city match by coordinates: {str(e)}")
            return False

    @staticmethod
    def find_nearby_entities(location, radius, entity_type, **kwargs):
        """
        Find entities (shops, specialists, etc.) near a location

        Args:
            location: Location instance or (lat, lng) tuple
            radius: Search radius in kilometers
            entity_type: Type of entity to find (shop, specialist, etc.)
            **kwargs: Additional filters

        Returns:
            List of entities with distance information
        """
        try:
            # Import entity models based on type
            if entity_type == "shop":
                from apps.shopapp.models import Shop

                model_class = Shop
                location_field = "location__coordinates"
            elif entity_type == "specialist":
                from apps.specialistsapp.models import Specialist

                model_class = Specialist
                location_field = "employee__shop__location__coordinates"
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")

            # Get reference point
            if isinstance(location, tuple):
                lat, lng = location
                point = Point(float(lng), float(lat), srid=4326)
            else:
                point = location.coordinates

            # Apply base filters
            queryset = model_class.objects.filter(
                Q(**{f"{location_field}__distance_lte": (point, D(km=radius))})
            )

            # Apply additional filters
            for key, value in kwargs.items():
                if key not in ["radius", "entity_type"] and value:
                    queryset = queryset.filter(**{key: value})

            # Annotate with distance
            queryset = queryset.annotate(distance=Distance(location_field, point)).order_by(
                "distance"
            )

            # Return with distance information
            result = []
            for entity in queryset:
                entity_data = {
                    "id": str(entity.id),
                    "name": entity.name,
                    "distance_km": entity.distance.km,
                }

                # Add travel time if requested
                if kwargs.get("include_travel_time"):
                    from .travel_time_service import TravelTimeService

                    entity_data["travel_time_minutes"] = TravelTimeService.estimate_travel_time(
                        point,
                        getattr(entity, location_field.split("__")[0]).coordinates,
                        mode="driving",
                    )

                result.append(entity_data)

            return result
        except Exception as e:
            logger.error(f"Error finding nearby entities: {str(e)}")
            raise

    @staticmethod
    def geocode_address(address, city=None, country=None):
        """
        Geocode an address to coordinates

        This is a simple implementation. In production, you'd want to use
        a proper geocoding service like Google Maps, MapBox, etc.
        """
        try:
            # Construct full address
            full_address = address
            if city:
                full_address += f", {city}"
            if country:
                full_address += f", {country}"

            # For production, integrate with a geocoding service
            # This is a placeholder implementation

            # For now, try to find in the database
            location_query = Q(address_line1__icontains=address)

            if city:
                city_obj = City.objects.filter(name__icontains=city).first()
                if city_obj:
                    location_query &= Q(city=city_obj)

            if country:
                country_obj = Country.objects.filter(
                    Q(name__icontains=country) | Q(code__iexact=country)
                ).first()
                if country_obj:
                    location_query &= Q(country=country_obj)

            # Try to find a match
            location = Location.objects.filter(location_query).first()

            if location:
                return {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "formatted_address": str(location),
                    "city": location.city.name,
                    "country": location.country.name,
                }

            # If no match found, return placeholder error
            return {"error": "Address not found"}
        except Exception as e:
            logger.error(f"Error geocoding address: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def reverse_geocode(latitude, longitude):
        """
        Reverse geocode coordinates to an address

        This is a simple implementation. In production, you'd want to use
        a proper geocoding service like Google Maps, MapBox, etc.
        """
        try:
            # Create a point
            point = Point(float(longitude), float(latitude), srid=4326)

            # Find nearest location
            location = (
                Location.objects.annotate(distance=Distance("coordinates", point))
                .order_by("distance")
                .first()
            )

            if location and location.distance.km < 0.5:  # Within 500m
                return {
                    "address": location.address_line1,
                    "city": location.city.name,
                    "country": location.country.name,
                    "postal_code": location.postal_code,
                    "place_name": location.place_name,
                }

            # If no exact match, just find the city
            city = (
                City.objects.annotate(distance=Distance("location", point))
                .order_by("distance")
                .first()
            )

            if city:
                return {"city": city.name, "country": city.country.name}

            # If no match found, return placeholder error
            return {"error": "Location not found"}
        except Exception as e:
            logger.error(f"Error reverse geocoding: {str(e)}")
            return {"error": str(e)}
