import logging
import math

from django.contrib.gis.geos import Point

from ..models import Location

logger = logging.getLogger(__name__)


class DistanceService:
    """Service for calculating distances and related metrics"""

    # Earth radius in kilometers
    EARTH_RADIUS_KM = 6371.0

    @staticmethod
    def calculate_haversine_distance(lat1, lng1, lat2, lng2):
        """
        Calculate the great-circle distance between two points
        on Earth using the Haversine formula

        Args:
            lat1, lng1: Coordinates of first point
            lat2, lng2: Coordinates of second point

        Returns:
            Distance in kilometers
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(float(lat1))
        lng1_rad = math.radians(float(lng1))
        lat2_rad = math.radians(float(lat2))
        lng2_rad = math.radians(float(lng2))

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in kilometers
        distance = DistanceService.EARTH_RADIUS_KM * c

        return distance

    @staticmethod
    def calculate_distance_matrix_by_ids(
        origin_id, destination_ids, include_travel_time=False
    ):
        """
        Calculate distances between an origin location and multiple destinations

        Args:
            origin_id: ID of origin location
            destination_ids: List of destination location IDs
            include_travel_time: Whether to include travel time estimates

        Returns:
            Dictionary with distances and travel times
        """
        try:
            # Get locations
            origin = Location.objects.get(id=origin_id)
            destinations = Location.objects.filter(id__in=destination_ids)

            results = []

            for dest in destinations:
                # Calculate distance using GeoDjango
                distance_km = (
                    origin.coordinates.distance(dest.coordinates) * 100
                )  # Convert to km

                result = {
                    "destination_id": str(dest.id),
                    "distance_km": round(distance_km, 2),
                }

                # Add travel time if requested
                if include_travel_time:
                    from .travel_time_service import TravelTimeService

                    result["travel_time_minutes"] = (
                        TravelTimeService.estimate_travel_time(
                            origin.coordinates, dest.coordinates
                        )
                    )

                results.append(result)

            return results
        except Location.DoesNotExist:
            logger.error(f"Location not found: {origin_id} or one of {destination_ids}")
            raise
        except Exception as e:
            logger.error(f"Error calculating distance matrix: {str(e)}")
            raise

    @staticmethod
    def calculate_distance_matrix_by_coordinates(
        origin_lat, origin_lng, destination_coords, include_travel_time=False
    ):
        """
        Calculate distances between an origin point and multiple destination coordinates

        Args:
            origin_lat, origin_lng: Origin coordinates
            destination_coords: List of (lat, lng) tuples
            include_travel_time: Whether to include travel time estimates

        Returns:
            Dictionary with distances and travel times
        """
        try:
            # Create origin point
            origin_point = Point(float(origin_lng), float(origin_lat), srid=4326)

            results = []

            for i, (dest_lat, dest_lng) in enumerate(destination_coords):
                # Create destination point
                dest_point = Point(float(dest_lng), float(dest_lat), srid=4326)

                # Calculate distance using Haversine formula
                distance_km = DistanceService.calculate_haversine_distance(
                    origin_lat, origin_lng, dest_lat, dest_lng
                )

                result = {
                    "destination_index": i,
                    "distance_km": round(distance_km, 2),
                }

                # Add travel time if requested
                if include_travel_time:
                    from .travel_time_service import TravelTimeService

                    result["travel_time_minutes"] = (
                        TravelTimeService.estimate_travel_time(origin_point, dest_point)
                    )

                results.append(result)

            return results
        except Exception as e:
            logger.error(f"Error calculating distance matrix by coordinates: {str(e)}")
            raise
