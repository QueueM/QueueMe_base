import logging
import math

from django.contrib.gis.geos import Point

logger = logging.getLogger(__name__)


class TravelTimeService:
    """Service for estimating travel times between locations"""

    # Default travel speeds by mode (km/h)
    DEFAULT_SPEEDS = {"walking": 5, "cycling": 15, "driving": 40, "transit": 25}

    # Traffic factor by time of day (multiplicative)
    TRAFFIC_FACTORS = {
        # Hour: factor
        7: 1.4,  # 7 AM rush hour
        8: 1.5,
        9: 1.3,
        16: 1.3,  # 4 PM rush hour
        17: 1.5,
        18: 1.4,
        19: 1.2,
    }

    @staticmethod
    def estimate_travel_time(origin, destination, mode="driving"):
        """
        Estimate travel time between two points

        Args:
            origin: Origin point (Point object or (lat, lng) tuple)
            destination: Destination point (Point object or (lat, lng) tuple)
            mode: Travel mode ('driving', 'walking', 'cycling', 'transit')

        Returns:
            Estimated travel time in minutes
        """
        try:
            # Convert to Point objects if needed
            if not isinstance(origin, Point):
                lat, lng = origin
                origin = Point(float(lng), float(lat), srid=4326)

            if not isinstance(destination, Point):
                lat, lng = destination
                destination = Point(float(lng), float(lat), srid=4326)

            # Calculate direct distance in kilometers
            from .distance_service import DistanceService

            distance_km = DistanceService.calculate_haversine_distance(
                origin.y, origin.x, destination.y, destination.x
            )

            # Get travel speed for mode
            speed_kmh = TravelTimeService.DEFAULT_SPEEDS.get(mode, 30)

            # Apply time-of-day traffic factor for driving
            if mode == "driving":
                import datetime

                current_hour = datetime.datetime.now().hour
                traffic_factor = TravelTimeService.TRAFFIC_FACTORS.get(current_hour, 1.0)
                speed_kmh = speed_kmh / traffic_factor

            # Calculate time in hours
            time_hours = distance_km / speed_kmh

            # Convert to minutes and round
            time_minutes = math.ceil(time_hours * 60)

            # Add fixed time components (traffic lights, turns, etc.)
            if mode == "driving":
                # Add 1 minute for every 2km (traffic lights, turns)
                time_minutes += distance_km // 2

                # Minimum time is 1 minute
                time_minutes = max(1, time_minutes)

            return time_minutes
        except Exception as e:
            logger.error(f"Error estimating travel time: {str(e)}")
            # Return fallback estimate
            return int(distance_km * 2)  # Simple fallback (2 min per km)

    @staticmethod
    def get_eta(origin, destination, departure_time=None):
        """
        Get estimated time of arrival

        Args:
            origin: Origin point
            destination: Destination point
            departure_time: Departure time (defaults to now)

        Returns:
            ETA as datetime
        """
        try:
            import datetime

            # Default to now if no departure time provided
            if departure_time is None:
                departure_time = datetime.datetime.now()

            # Get travel time in minutes
            travel_time_minutes = TravelTimeService.estimate_travel_time(
                origin, destination, mode="driving"
            )

            # Calculate ETA
            eta = departure_time + datetime.timedelta(minutes=travel_time_minutes)

            return eta
        except Exception as e:
            logger.error(f"Error calculating ETA: {str(e)}")
            # Return fallback
            return departure_time + datetime.timedelta(minutes=30)
