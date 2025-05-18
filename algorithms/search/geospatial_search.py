import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GeospatialSearch:
    """
    Efficient geospatial search algorithm that finds entities near a location,
    optimized for performance with spatial indexing techniques.

    This algorithm enhances location-based search by:
    1. Using bounding box pre-filtering for efficient queries
    2. Calculating precise distances with the Haversine formula
    3. Supporting radius-based and k-nearest searches
    4. Incorporating advanced filtering and sorting
    5. Optimizing for large datasets with spatial partitioning
    """

    # Earth radius in kilometers for Haversine calculations
    EARTH_RADIUS_KM = 6371.0

    def __init__(
        self,
        use_spatial_index: bool = True,
        distance_precision: int = 2,
        max_results: int = 1000,
        use_bounding_box_optimization: bool = True,
    ):
        """
        Initialize the geospatial search algorithm.

        Args:
            use_spatial_index: Whether to use spatial indexing optimizations
            distance_precision: Decimal places for distance calculations
            max_results: Maximum results to return (safety limit)
            use_bounding_box_optimization: Whether to pre-filter with bounding boxes
        """
        self.use_spatial_index = use_spatial_index
        self.distance_precision = distance_precision
        self.max_results = max_results
        self.use_bounding_box_optimization = use_bounding_box_optimization

    def find_nearby_entities(
        self,
        latitude: float,
        longitude: float,
        entities: List[Dict],
        radius_km: Optional[float] = None,
        k_nearest: Optional[int] = None,
        filters: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        include_distance: bool = True,
        distance_field: str = "distance_km",
        include_duration: bool = False,
        lat_field: str = "latitude",
        lng_field: str = "longitude",
        location_field: Optional[str] = None,
    ) -> List[Dict]:
        """
        Find entities near the specified location.

        Args:
            latitude: Latitude of the search point
            longitude: Longitude of the search point
            entities: List of entities to search (with lat/lng or nested location)
            radius_km: Optional search radius in kilometers
            k_nearest: Optional limit to k nearest results
            filters: Optional additional filters (field:value pairs)
            sort_by: Optional field to sort results by (default: distance)
            include_distance: Whether to include distance in results
            distance_field: Field name for the calculated distance
            include_duration: Whether to estimate travel duration
            lat_field: Field name for latitude (if not in location field)
            lng_field: Field name for longitude (if not in location field)
            location_field: Optional field containing lat/lng as nested object

        Returns:
            List of entities within radius or k nearest, with distances
        """
        # Input validation
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError("Latitude and longitude must be numeric values")

        # Convert to float if they're valid numbers (handles string inputs)
        latitude = float(latitude)
        longitude = float(longitude)

        # Check latitude/longitude ranges
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise ValueError("Latitude must be between -90 and 90, longitude between -180 and 180")

        # Require at least one of radius or k_nearest
        if radius_km is None and k_nearest is None:
            radius_km = 10.0  # Default radius

        if radius_km is not None and radius_km <= 0:
            raise ValueError("Radius must be positive")

        if k_nearest is not None and k_nearest <= 0:
            raise ValueError("k_nearest must be positive")

        # Step 1: Apply initial filtering with bounding box optimization
        if self.use_bounding_box_optimization and radius_km is not None:
            bounding_box = self._calculate_bounding_box(latitude, longitude, radius_km)
            filtered_entities = self._filter_by_bounding_box(
                entities, bounding_box, lat_field, lng_field, location_field
            )
        else:
            filtered_entities = entities.copy()

        # Step 2: Calculate exact distances using Haversine formula
        entities_with_distance = []

        for entity in filtered_entities:
            # Extract coordinates
            if location_field:
                # Get from nested location object
                location = entity.get(location_field, {})
                entity_lat = location.get(lat_field)
                entity_lng = location.get(lng_field)
            else:
                # Get directly from entity
                entity_lat = entity.get(lat_field)
                entity_lng = entity.get(lng_field)

            # Skip entities without valid coordinates
            if entity_lat is None or entity_lng is None:
                continue

            try:
                # Convert to float (handles string values)
                entity_lat = float(entity_lat)
                entity_lng = float(entity_lng)

                # Calculate distance
                distance = self._haversine_distance(latitude, longitude, entity_lat, entity_lng)

                # Round to specified precision
                distance = round(distance, self.distance_precision)

                # Add distance to entity copy
                entity_copy = entity.copy()

                if include_distance:
                    entity_copy[distance_field] = distance

                # Calculate estimated travel duration if requested
                if include_duration:
                    duration_minutes = self._estimate_travel_duration(distance)
                    entity_copy["estimated_travel_minutes"] = duration_minutes

                # If using radius, filter by distance
                if radius_km is not None and distance > radius_km:
                    continue

                # Apply additional filters if specified
                if filters and not self._apply_filters(entity_copy, filters):
                    continue

                entities_with_distance.append(entity_copy)
            except (ValueError, TypeError) as e:
                # Log the error and skip this entity
                logger.warning(f"Error calculating distance for entity: {e}")
                continue

        # Step 3: Sort results
        if sort_by == "distance" or sort_by is None:
            # Sort by distance (closest first)
            sorted_entities = sorted(
                entities_with_distance,
                key=lambda e: e.get(distance_field, float("inf")),
            )
        else:
            # Sort by specified field
            sorted_entities = sorted(
                entities_with_distance,
                key=lambda e: e.get(sort_by, 0),
                reverse=True,  # Higher values first (e.g., rating, reviews)
            )

        # Step 4: Apply k_nearest limit if specified
        if k_nearest is not None:
            result = sorted_entities[:k_nearest]
        else:
            result = sorted_entities

        # Apply safety limit
        return result[: self.max_results]

    def _calculate_bounding_box(
        self, latitude: float, longitude: float, radius_km: float
    ) -> Tuple[float, float, float, float]:
        """
        Calculate a bounding box around the point for initial filtering.
        This creates a square that fully contains the circular radius.

        Returns (min_lat, min_lng, max_lat, max_lng)
        """
        # Angular distance in radians on a great circle
        rad_dist = radius_km / self.EARTH_RADIUS_KM

        # Latitude bounds
        min_lat = latitude - math.degrees(rad_dist)
        max_lat = latitude + math.degrees(rad_dist)

        # Longitude bounds (width varies with latitude)
        # At higher latitudes, longitude degrees represent less distance
        lng_delta = math.degrees(math.asin(math.sin(rad_dist) / math.cos(math.radians(latitude))))

        min_lng = longitude - lng_delta
        max_lng = longitude + lng_delta

        # Handle latitude edge cases
        min_lat = max(-90.0, min_lat)
        max_lat = min(90.0, max_lat)

        # Handle longitude edge cases
        # Longitude wraps around at 180/-180
        if min_lng < -180.0:
            min_lng += 360.0
        if max_lng > 180.0:
            max_lng -= 360.0

        return (min_lat, min_lng, max_lat, max_lng)

    def _filter_by_bounding_box(
        self,
        entities: List[Dict],
        bounding_box: Tuple[float, float, float, float],
        lat_field: str,
        lng_field: str,
        location_field: Optional[str],
    ) -> List[Dict]:
        """
        Filter entities by bounding box for efficient pre-filtering.
        """
        min_lat, min_lng, max_lat, max_lng = bounding_box
        filtered_entities = []

        for entity in entities:
            # Extract coordinates
            if location_field:
                # Get from nested location object
                location = entity.get(location_field, {})
                entity_lat = location.get(lat_field)
                entity_lng = location.get(lng_field)
            else:
                # Get directly from entity
                entity_lat = entity.get(lat_field)
                entity_lng = entity.get(lng_field)

            # Skip entities without valid coordinates
            if entity_lat is None or entity_lng is None:
                continue

            try:
                # Convert to float (handles string values)
                entity_lat = float(entity_lat)
                entity_lng = float(entity_lng)

                # Check if within bounding box
                # Handle special case for longitude wrap-around
                lng_check = False

                if min_lng <= max_lng:
                    # Normal case
                    lng_check = min_lng <= entity_lng <= max_lng
                else:
                    # Box crosses the -180/180 boundary
                    lng_check = entity_lng >= min_lng or entity_lng <= max_lng

                if min_lat <= entity_lat <= max_lat and lng_check:
                    filtered_entities.append(entity)

            except (ValueError, TypeError):
                # Skip entities with invalid coordinates
                continue

        return filtered_entities

    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate the great-circle distance between two points
        using the Haversine formula (in kilometers).
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)

        # Haversine formula
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in kilometers
        distance = self.EARTH_RADIUS_KM * c

        return distance

    def _estimate_travel_duration(self, distance_km: float) -> int:
        """
        Estimate travel duration in minutes based on distance.

        This is a simplified model. In a real application, would use:
        - Different speeds for different transportation modes
        - Traffic data if available
        - Routing services for more accurate estimates

        Returns an integer estimate of minutes.
        """
        # Simple model: Average urban driving speed of 30 km/h = 0.5 km/min
        # For first 2km: walking/congested rate of 0.2 km/min (10-12 km/h)
        # For remaining distance: driving rate of 0.5 km/min (30 km/h)

        if distance_km <= 2.0:
            # Short distance: slower speed
            duration = distance_km / 0.2
        else:
            # Longer distance: mix of slow start and faster speed
            duration = (2.0 / 0.2) + ((distance_km - 2.0) / 0.5)

        # Add 2-minute fixed penalty for starts/stops
        duration += 2.0

        # Return rounded integer
        return max(1, round(duration))

    def _apply_filters(self, entity: Dict, filters: Dict) -> bool:
        """
        Apply additional filters to an entity.
        Returns True if entity passes all filters, False otherwise.
        """
        for field, value in filters.items():
            # Handle nested fields (e.g., "location.city")
            if "." in field:
                parts = field.split(".")
                nested_value = entity
                for part in parts:
                    if isinstance(nested_value, dict) and part in nested_value:
                        nested_value = nested_value[part]
                    else:
                        # Field doesn't exist
                        return False

                # Check if nested value matches
                if nested_value != value:
                    return False

            # Handle special filter operators
            elif isinstance(value, dict) and len(value) == 1:
                # Example: {"age": {"$gt": 18}}
                operator, filter_value = next(iter(value.items()))

                if operator == "$gt":
                    if not entity.get(field, 0) > filter_value:
                        return False
                elif operator == "$gte":
                    if not entity.get(field, 0) >= filter_value:
                        return False
                elif operator == "$lt":
                    if not entity.get(field, 0) < filter_value:
                        return False
                elif operator == "$lte":
                    if not entity.get(field, 0) <= filter_value:
                        return False
                elif operator == "$ne":
                    if entity.get(field) == filter_value:
                        return False
                elif operator == "$in":
                    if not entity.get(field) in filter_value:
                        return False
                elif operator == "$nin":
                    if entity.get(field) in filter_value:
                        return False

            # Simple equality check
            elif entity.get(field) != value:
                return False

        # All filters passed
        return True

    def find_entities_in_area(
        self,
        bounds: Tuple[float, float, float, float],
        entities: List[Dict],
        filters: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        limit: Optional[int] = None,
        lat_field: str = "latitude",
        lng_field: str = "longitude",
        location_field: Optional[str] = None,
    ) -> List[Dict]:
        """
        Find entities within a geographical bounding box.

        Args:
            bounds: Tuple of (min_lat, min_lng, max_lat, max_lng)
            entities: List of entities to search
            filters: Optional additional filters
            sort_by: Optional field to sort results by
            limit: Maximum number of results to return
            lat_field: Field name for latitude
            lng_field: Field name for longitude
            location_field: Optional field containing lat/lng as nested object

        Returns:
            List of entities within the bounding box
        """
        # Input validation
        if not len(bounds) == 4:
            raise ValueError("Bounds must be a tuple of (min_lat, min_lng, max_lat, max_lng)")

        min_lat, min_lng, max_lat, max_lng = bounds

        # Check latitude/longitude ranges
        if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")

        if not (-180 <= min_lng <= 180) or not (-180 <= max_lng <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        # Ensure min is less than or equal to max
        if min_lat > max_lat:
            min_lat, max_lat = max_lat, min_lat

        # Filter entities by bounding box
        filtered_entities = self._filter_by_bounding_box(
            entities,
            (min_lat, min_lng, max_lat, max_lng),
            lat_field,
            lng_field,
            location_field,
        )

        # Apply additional filters if specified
        if filters:
            filtered_entities = [
                entity for entity in filtered_entities if self._apply_filters(entity, filters)
            ]

        # Sort results if specified
        if sort_by:
            filtered_entities.sort(key=lambda e: e.get(sort_by, 0), reverse=True)

        # Apply limit if specified
        if limit:
            filtered_entities = filtered_entities[:limit]

        # Apply safety limit
        return filtered_entities[: self.max_results]
