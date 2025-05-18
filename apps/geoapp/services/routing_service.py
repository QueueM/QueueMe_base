import logging
import uuid

import polyline
from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.utils.translation import gettext_lazy as _

from ..models import Location

logger = logging.getLogger(__name__)


class RoutingService:
    """Service for advanced routing operations and path planning"""

    # Default route types
    ROUTE_TYPES = {
        "fastest": _("Fastest Route"),
        "shortest": _("Shortest Route"),
        "eco": _("Eco-friendly Route"),
        "scenic": _("Scenic Route"),
    }

    # Avoid options
    AVOID_OPTIONS = {
        "highways": _("Highways"),
        "tolls": _("Toll Roads"),
        "ferries": _("Ferries"),
        "indoor": _("Indoor Steps"),
    }

    @staticmethod
    def calculate_route(
        origin,
        destination,
        waypoints=None,
        route_type="fastest",
        avoid=None,
        departure_time=None,
    ):
        """
        Calculate a route between two points

        Args:
            origin: Origin point (Point object, Location ID, or (lat, lng) tuple)
            destination: Destination point (Point object, Location ID, or (lat, lng) tuple)
            waypoints: Optional list of waypoints (Point objects, Location IDs, or (lat, lng) tuples)
            route_type: Type of route ('fastest', 'shortest', 'eco', 'scenic')
            avoid: List of features to avoid ('highways', 'tolls', 'ferries', 'indoor')
            departure_time: Departure time (datetime object) for traffic consideration

        Returns:
            Dictionary with route information
        """
        try:
            # Convert origin and destination to coordinates
            origin_coords = RoutingService._get_coordinates(origin)
            destination_coords = RoutingService._get_coordinates(destination)

            # Convert waypoints to coordinates if provided
            waypoint_coords = []
            if waypoints:
                for waypoint in waypoints:
                    waypoint_coords.append(RoutingService._get_coordinates(waypoint))

            # In a production environment, we would use a routing API (like Google Maps, MapBox, etc.)
            # For this implementation, we'll create a simplified routing algorithm

            # Check if we should use an external routing API if configured
            if hasattr(settings, "ROUTING_API_KEY") and settings.ROUTING_API_KEY:
                route_data = RoutingService._call_external_routing_api(
                    origin_coords,
                    destination_coords,
                    waypoint_coords,
                    route_type,
                    avoid,
                    departure_time,
                )
            else:
                # Use our simple implementation
                route_data = RoutingService._calculate_simple_route(
                    origin_coords, destination_coords, waypoint_coords, route_type
                )

            return route_data
        except Exception as e:
            logger.error(f"Error calculating route: {str(e)}")
            raise

    @staticmethod
    def get_turn_by_turn_directions(route_data):
        """
        Extract turn-by-turn directions from route data

        Args:
            route_data: Route data from calculate_route

        Returns:
            List of direction steps
        """
        try:
            if "steps" in route_data:
                # Route data already has steps
                return route_data["steps"]

            # If no steps data is available, generate simplified directions
            steps = []
            if "path" in route_data and len(route_data["path"]) >= 2:
                path = route_data["path"]

                # Calculate direction between each pair of points
                for i in range(len(path) - 1):
                    from_point = path[i]
                    to_point = path[i + 1]

                    # Calculate bearing between points
                    direction = RoutingService._get_direction(
                        from_point[0], from_point[1], to_point[0], to_point[1]
                    )

                    # Calculate distance between points
                    from ..services.distance_service import DistanceService

                    distance = DistanceService.calculate_haversine_distance(
                        from_point[0], from_point[1], to_point[0], to_point[1]
                    )

                    steps.append(
                        {
                            "instruction": direction,
                            "distance": round(distance, 2),
                            "duration": round(
                                distance * 1.5, 1
                            ),  # Simple estimation (1.5 minutes per km)
                            "start_location": from_point,
                            "end_location": to_point,
                        }
                    )

            return steps
        except Exception as e:
            logger.error(f"Error generating turn-by-turn directions: {str(e)}")
            return []

    @staticmethod
    def get_route_geometry(route_data, format="geojson"):
        """
        Get route geometry in specified format

        Args:
            route_data: Route data from calculate_route
            format: Output format ('geojson', 'polyline', 'wkt')

        Returns:
            Route geometry in specified format
        """
        try:
            if "path" not in route_data or not route_data["path"]:
                return None

            # Extract coordinates from path
            coordinates = route_data["path"]

            if format == "geojson":
                # Create GeoJSON structure
                geojson = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[lng, lat] for lat, lng in coordinates],
                    },
                    "properties": {
                        "distance_km": route_data.get("distance_km", 0),
                        "duration_minutes": route_data.get("duration_minutes", 0),
                    },
                }
                return geojson

            elif format == "polyline":
                # Encode as Google polyline format
                return polyline.encode(coordinates)

            elif format == "wkt":
                # Create LineString from coordinates
                line = LineString([Point(lng, lat) for lat, lng in coordinates])
                return line.wkt

            else:
                raise ValueError(f"Unsupported format: {format}")
        except Exception as e:
            logger.error(f"Error generating route geometry: {str(e)}")
            return None

    @staticmethod
    def optimize_waypoints(origin, destination, waypoints, optimization_type="shortest"):
        """
        Optimize the order of waypoints for a route

        Args:
            origin: Origin point
            destination: Destination point
            waypoints: List of waypoints to visit
            optimization_type: Type of optimization ('shortest', 'fastest')

        Returns:
            Optimized list of waypoints
        """
        try:
            # For a simple implementation, we'll use a greedy algorithm (nearest neighbor)
            # For more complex optimization, algorithms like simulated annealing or
            # genetic algorithms would be more appropriate

            # Convert all points to coordinates
            origin_coords = RoutingService._get_coordinates(origin)
            # unused_unused_destination_coords = RoutingService._get_coordinates(destination)

            waypoint_coords = []
            for waypoint in waypoints:
                waypoint_coords.append(RoutingService._get_coordinates(waypoint))

            # Start with the origin
            current_point = origin_coords
            remaining_waypoints = waypoint_coords.copy()
            optimized_waypoints = []

            # Find the nearest waypoint each time
            while remaining_waypoints:
                # Find the nearest waypoint to current point
                nearest_idx, nearest_dist = RoutingService._find_nearest_waypoint(
                    current_point, remaining_waypoints
                )

                # Add the nearest waypoint to optimized list
                optimized_waypoints.append(remaining_waypoints[nearest_idx])

                # Update current point
                current_point = remaining_waypoints[nearest_idx]

                # Remove from remaining waypoints
                remaining_waypoints.pop(nearest_idx)

            return optimized_waypoints
        except Exception as e:
            logger.error(f"Error optimizing waypoints: {str(e)}")
            return waypoints  # Return original waypoints in case of error

    @staticmethod
    def isochrone(center, travel_times, mode="driving", departure_time=None):
        """
        Calculate isochrone polygons (areas reachable within given travel times)

        Args:
            center: Center point
            travel_times: List of travel times in minutes
            mode: Travel mode ('driving', 'walking', 'cycling', 'transit')
            departure_time: Departure time for traffic consideration

        Returns:
            Dictionary with isochrone polygons for each time
        """
        try:
            # This is a simplified placeholder implementation
            # Real implementation would use a specialized API or algorithm

            # Convert center to coordinates
            center_coords = RoutingService._get_coordinates(center)

            # For each travel time, estimate the reachable distance
            from ..services.travel_time_service import TravelTimeService

            result = {}

            for time_minutes in travel_times:
                # Estimate distance that can be covered in given time
                speed_kmh = TravelTimeService.DEFAULT_SPEEDS.get(mode, 30)

                # Apply time-of-day adjustment if needed
                if mode == "driving" and departure_time:
                    hour = departure_time.hour
                    traffic_factor = TravelTimeService.TRAFFIC_FACTORS.get(hour, 1.0)
                    speed_kmh = speed_kmh / traffic_factor

                # Convert time to hours
                time_hours = time_minutes / 60

                # Calculate approximate radius in km
                radius_km = speed_kmh * time_hours

                # In a real implementation, we would generate an actual polygon based on road network
                # For this simple implementation, we'll just provide the radius
                result[time_minutes] = {
                    "center": center_coords,
                    "radius_km": radius_km,
                    "travel_time_minutes": time_minutes,
                }

            return result
        except Exception as e:
            logger.error(f"Error calculating isochrone: {str(e)}")
            raise

    @staticmethod
    def find_optimal_meeting_point(points, constraints=None):
        """
        Find an optimal meeting point for multiple locations

        Args:
            points: List of points (coordinates or Location IDs)
            constraints: Optional constraints (e.g., must be a coffee shop)

        Returns:
            Optimal meeting point coordinates and estimated travel times
        """
        try:
            # Convert points to coordinates
            coords = []
            for point in points:
                coords.append(RoutingService._get_coordinates(point))

            # Simple implementation: find the centroid
            lat_sum = sum(lat for lat, _ in coords)
            lng_sum = sum(lng for _, lng in coords)

            centroid = (lat_sum / len(coords), lng_sum / len(coords))

            # Calculate travel times from each point to centroid
            travel_times = []

            for point in coords:
                from ..services.travel_time_service import TravelTimeService

                time_minutes = TravelTimeService.estimate_travel_time(
                    point, centroid, mode="driving"
                )

                travel_times.append(time_minutes)

            # Find nearby points of interest if constraints provided
            poi = None
            if constraints:
                # This would require integration with a places API
                # For now, we'll return a placeholder
                poi = {
                    "name": "Nearby coffee shop",
                    "coordinates": centroid,
                    "distance_from_centroid": 0.5,
                }

            return {
                "optimal_point": centroid,
                "travel_times": travel_times,
                "average_travel_time": sum(travel_times) / len(travel_times),
                "point_of_interest": poi,
            }
        except Exception as e:
            logger.error(f"Error finding optimal meeting point: {str(e)}")
            raise

    # Helper methods

    @staticmethod
    def _get_coordinates(point):
        """Convert different point formats to (lat, lng) tuple"""
        if isinstance(point, tuple) and len(point) == 2:
            # Already a (lat, lng) tuple
            return point

        elif isinstance(point, Point):
            # GeoDjango Point object
            return (point.y, point.x)

        elif isinstance(point, str) or isinstance(point, uuid.UUID):
            # Location ID
            try:
                location = Location.objects.get(id=point)
                return (location.latitude, location.longitude)
            except Location.DoesNotExist:
                raise ValueError(f"Location not found: {point}")

        else:
            raise ValueError(f"Unsupported point format: {point}")

    @staticmethod
    def _calculate_simple_route(origin, destination, waypoints=None, route_type="fastest"):
        """
        Calculate a simplified route (without external API)

        This is a placeholder implementation that generates a straight line path
        with some intermediate points. In a real implementation, this would use
        actual road network data.
        """
        # Create a path with interpolated points
        path = [origin]

        # Add waypoints if provided
        if waypoints:
            path.extend(waypoints)

        # Add some intermediate points between last point and destination
        from ..services.distance_service import DistanceService

        last_point = path[-1]

        # Calculate straight-line distance
        distance = DistanceService.calculate_haversine_distance(
            last_point[0], last_point[1], destination[0], destination[1]
        )

        # Add intermediate points for longer distances
        if distance > 5:
            # Number of points to add (1 point per 5km)
            num_points = min(10, int(distance / 5))

            for i in range(1, num_points + 1):
                fraction = i / (num_points + 1)

                # Interpolate between last point and destination
                lat = last_point[0] + (destination[0] - last_point[0]) * fraction
                lng = last_point[1] + (destination[1] - last_point[1]) * fraction

                path.append((lat, lng))

        # Add destination
        path.append(destination)

        # Calculate total distance
        total_distance = 0
        for i in range(len(path) - 1):
            segment_distance = DistanceService.calculate_haversine_distance(
                path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]
            )
            total_distance += segment_distance

        # Estimate duration (using TravelTimeService)
        from ..services.travel_time_service import TravelTimeService

        duration = TravelTimeService.estimate_travel_time(origin, destination, mode="driving")

        return {
            "path": path,
            "distance_km": round(total_distance, 2),
            "duration_minutes": duration,
            "route_type": route_type,
        }

    @staticmethod
    def _call_external_routing_api(
        origin,
        destination,
        waypoints=None,
        route_type="fastest",
        avoid=None,
        departure_time=None,
    ):
        """
        Call an external routing API (placeholder)

        In a real implementation, this would integrate with Google Maps, MapBox,
        or another routing API. This is just a placeholder.
        """
        # This is a placeholder implementation
        logger.info("External routing API would be called here in production")

        # Fall back to simple implementation
        return RoutingService._calculate_simple_route(origin, destination, waypoints, route_type)

    @staticmethod
    def _find_nearest_waypoint(point, waypoints):
        """
        Find the nearest waypoint to a given point

        Args:
            point: Reference point (lat, lng)
            waypoints: List of waypoints (lat, lng)

        Returns:
            Tuple of (index, distance) for the nearest waypoint
        """
        from ..services.distance_service import DistanceService

        nearest_idx = 0
        nearest_dist = float("inf")

        for i, waypoint in enumerate(waypoints):
            dist = DistanceService.calculate_haversine_distance(
                point[0], point[1], waypoint[0], waypoint[1]
            )

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        return nearest_idx, nearest_dist

    @staticmethod
    def _get_direction(lat1, lng1, lat2, lng2):
        """
        Get a human-readable direction between two points

        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates

        Returns:
            Direction description
        """
        import math

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)

        # Calculate bearing
        y = math.sin(lng2_rad - lng1_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
            lat2_rad
        ) * math.cos(lng2_rad - lng1_rad)
        bearing = math.atan2(y, x)

        # Convert to degrees
        bearing_deg = math.degrees(bearing)
        if bearing_deg < 0:
            bearing_deg += 360

        # Convert to cardinal direction
        directions = [
            "north",
            "northeast",
            "east",
            "southeast",
            "south",
            "southwest",
            "west",
            "northwest",
            "north",
        ]
        index = round(bearing_deg / 45)

        # Calculate distance
        from ..services.distance_service import DistanceService

        distance = DistanceService.calculate_haversine_distance(lat1, lng1, lat2, lng2)

        # Format instruction based on direction and distance
        direction = directions[index]

        if distance < 0.1:
            return f"Continue straight for {int(distance * 1000)} meters"
        elif distance < 1:
            return f"Head {direction} for {int(distance * 1000)} meters"
        else:
            return f"Travel {direction} for {round(distance, 1)} km"
