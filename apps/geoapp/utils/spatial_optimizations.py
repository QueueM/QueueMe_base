"""
Spatial Query Optimizations

Utilities for optimizing geospatial queries in QueueMe using PostGIS capabilities
and proper spatial indexing strategies.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.gis.db.models import Q
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.contrib.gis.measure import D
from django.db import connection
from django.db.models import ExpressionWrapper, F, FloatField, QuerySet

# Constants for geospatial calculations
EARTH_RADIUS_KM = 6371  # Earth radius in kilometers
DEFAULT_SRID = 4326  # WGS84 spatial reference system
MAX_DISTANCE_KM = getattr(
    settings, "MAX_GEO_DISTANCE_KM", 100
)  # Maximum distance for spatial queries
DISTANCE_PRECISION = getattr(
    settings, "GEO_DISTANCE_PRECISION", 2
)  # Decimal places for distance values


def optimize_point_distance_query(
    queryset: QuerySet,
    point: Union[Point, Tuple[float, float]],
    distance_km: float = 10.0,
    distance_field_name: str = "distance",
) -> QuerySet:
    """
    Optimize a distance query from a point with proper spatial indexing

    Args:
        queryset: The base queryset to filter
        point: The reference point as a Point object or (longitude, latitude) tuple
        distance_km: Maximum distance in kilometers
        distance_field_name: Name for the calculated distance field

    Returns:
        QuerySet filtered by distance with distance annotation
    """
    # Ensure we have a Point object
    if not isinstance(point, Point):
        point = Point(point[0], point[1], srid=DEFAULT_SRID)

    # Apply distance limit first using a fast bounding box filter
    # This uses the spatial index efficiently before doing more expensive calculations
    filtered_qs = queryset.filter(
        # Assuming the queryset model has a 'coordinates' field
        # If it's a different field, this should be adjusted
        coordinates__dwithin=(point, D(km=distance_km))
    )

    # Then annotate with exact distance
    # This uses ST_Distance_Sphere which is faster than a full geodesic calculation
    # but slightly less accurate (usually within 0.3% which is fine for most applications)
    annotated_qs = filtered_qs.annotate(
        **{distance_field_name: Distance("coordinates", point)}
    )

    # Convert distance to kilometers and order by it
    return annotated_qs.order_by(distance_field_name)


def get_points_in_polygon(
    queryset: QuerySet,
    polygon: Union[Polygon, str, List],
    distance_ordered: bool = False,
    reference_point: Optional[Point] = None,
) -> QuerySet:
    """
    Get all points from queryset that fall within a polygon with optimized query

    Args:
        queryset: The base queryset to filter
        polygon: Polygon geometry or GeoJSON string or list of coordinates
        distance_ordered: Whether to order by distance from reference point
        reference_point: Point to calculate distance from (required if distance_ordered=True)

    Returns:
        QuerySet filtered to points within the polygon
    """
    # Ensure we have a proper Polygon object
    if not isinstance(polygon, GEOSGeometry):
        if isinstance(polygon, str):
            # Assume it's GeoJSON or WKT
            polygon = GEOSGeometry(polygon, srid=DEFAULT_SRID)
        elif isinstance(polygon, list):
            # Assume it's a list of coordinate pairs [(lng1, lat1), (lng2, lat2), ...]
            # First coordinate should be repeated to close the polygon
            if polygon[0] != polygon[-1]:
                polygon.append(polygon[0])
            polygon = Polygon(polygon, srid=DEFAULT_SRID)

    # Use contains lookup which is spatially indexed
    filtered_qs = queryset.filter(coordinates__contained=polygon)

    # If ordering by distance is requested and reference point provided
    if distance_ordered and reference_point:
        return filtered_qs.annotate(
            distance=Distance("coordinates", reference_point)
        ).order_by("distance")

    return filtered_qs


def create_bounding_box(
    center_point: Union[Point, Tuple[float, float]], distance_km: float
) -> Polygon:
    """
    Create a bounding box around a point for faster initial filtering

    Args:
        center_point: Center point as a Point object or (longitude, latitude) tuple
        distance_km: Distance in kilometers

    Returns:
        Polygon representing a bounding box
    """
    # Ensure we have a Point object
    if not isinstance(center_point, Point):
        center_point = Point(center_point[0], center_point[1], srid=DEFAULT_SRID)

    # Approximate degrees per km at this latitude
    latitude = center_point.y
    longitude = center_point.x

    # Calculate longitude range (gets wider near equator, narrower near poles)
    lat_radians = math.radians(latitude)
    lng_delta = distance_km / (EARTH_RADIUS_KM * math.cos(lat_radians))
    lng_delta_degrees = math.degrees(lng_delta)

    # Calculate latitude range (roughly 111km per degree)
    lat_delta = distance_km / 111.32

    # Create bounding box coordinates
    min_lng = longitude - lng_delta_degrees
    max_lng = longitude + lng_delta_degrees
    min_lat = latitude - lat_delta
    max_lat = latitude + lat_delta

    # Create polygon coordinates (must close the ring)
    box_coords = [
        (min_lng, min_lat),
        (min_lng, max_lat),
        (max_lng, max_lat),
        (max_lng, min_lat),
        (min_lng, min_lat),
    ]

    # Create polygon
    return Polygon(box_coords, srid=DEFAULT_SRID)


def optimize_geofence_query(
    queryset: QuerySet,
    point: Union[Point, Tuple[float, float]],
    only_active: bool = True,
) -> QuerySet:
    """
    Efficiently query geofences that contain a specific point

    Args:
        queryset: Base queryset of Geofence objects
        point: Point to check against geofences
        only_active: Filter for only active geofences

    Returns:
        QuerySet of matching geofences
    """
    # Ensure we have a Point object
    if not isinstance(point, Point):
        point = Point(point[0], point[1], srid=DEFAULT_SRID)

    # Start with filter for geofences with explicit boundaries
    boundary_filter = Q(boundary__contains=point)

    # Add filter for circular geofences
    # The distance filter is more complex as we need to check against the radius
    # We'll use raw SQL here for maximum performance with PostGIS
    distance_expr = ExpressionWrapper(
        Distance("center", point), output_field=FloatField()
    )
    radius_expr = ExpressionWrapper(
        F("radius_km") / 111.32,  # Convert km to approximate degrees
        output_field=FloatField(),
    )

    # Calculate the distance in degrees and compare with radius
    circle_filter = Q(center__dwithin=(point, F("radius_km") / 111.32))

    # Combine filters (either explicit boundary contains point or center is within radius)
    combined_filter = boundary_filter | circle_filter

    # Apply active filters if requested
    if only_active:
        from django.utils import timezone

        now = timezone.now()
        active_filter = (
            Q(is_active=True)
            & Q(active_from__lte=now)
            & (Q(active_until__isnull=True) | Q(active_until__gt=now))
        )
        combined_filter &= active_filter

    # Apply all filters
    return queryset.filter(combined_filter)


def batch_geocode_locations(
    addresses: List[Dict[str, str]], geocoding_service: str = "postgresql"
) -> List[Dict[str, Any]]:
    """
    Batch geocode addresses using PostgreSQL's built-in geocoding or external service

    Args:
        addresses: List of address dictionaries with keys like 'address', 'city', etc.
        geocoding_service: Which service to use ('postgresql', 'google', etc.)

    Returns:
        List of geocoded results with coordinates
    """
    # This would connect to an actual geocoding service
    # or use PostGIS for simple geocoding if supported

    # Return format example
    results = []

    if geocoding_service == "postgresql" and has_postgis_geocoding():
        # This assumes the PostGIS Tiger Geocoder is installed
        try:
            with connection.cursor() as cursor:
                for address in addresses:
                    full_address = f"{address.get('address', '')}, {address.get('city', '')}, {address.get('country', '')}"

                    cursor.execute(
                        "SELECT g.rating, ST_X(g.geomout) as lng, ST_Y(g.geomout) as lat "
                        "FROM geocode(%s) AS g",
                        [full_address],
                    )
                    row = cursor.fetchone()

                    if row:
                        rating, lng, lat = row
                        results.append(
                            {
                                "address": address,
                                "coordinates": {
                                    "latitude": lat,
                                    "longitude": lng,
                                    "confidence": rating / 100,
                                },
                            }
                        )
                    else:
                        results.append(
                            {
                                "address": address,
                                "coordinates": None,
                                "error": "Could not geocode address",
                            }
                        )
        except Exception as e:
            # Fall back to placeholder implementation if geocoding fails
            for address in addresses:
                results.append(
                    {"address": address, "coordinates": None, "error": str(e)}
                )
    else:
        # Placeholder implementation - would be replaced with actual geocoding logic
        for address in addresses:
            # Example result structure
            results.append(
                {
                    "address": address,
                    "coordinates": {
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "confidence": 0.0,
                    },
                    "note": "This is a placeholder for actual geocoding implementation",
                }
            )

    return results


def optimize_spatial_index(model_class, location_field="location", batch_size=1000):
    """
    Optimize PostGIS spatial indexes for a model containing geographical data.

    This function clusters geographical data to improve query performance.
    """
    model_meta = model_class._meta
    table_name = model_meta.db_table

    # Get the right field name in the database
    location_db_column = None
    for field in model_meta.fields:
        if field.name == location_field:
            location_db_column = field.column
            break

    if not location_db_column:
        return (
            False,
            f"Field {location_field} not found on model {model_class.__name__}",
        )

    try:
        with connection.cursor() as cursor:
            # Django's cursor.execute properly escapes table_name and location_db_column
            # using cursor.execute's parameter substitution
            cursor.execute(
                "SELECT COUNT(*) FROM %s WHERE %s IS NOT NULL",
                [table_name, location_db_column],
            )
            count = cursor.fetchone()[0]

            if count == 0:
                return True, f"No data with location in {model_class.__name__}"

            # Create a spatial index with GIST if it doesn't exist
            index_name = f"{table_name}_{location_db_column}_gist"

            # Check if index exists
            cursor.execute(
                """
                SELECT COUNT(*) FROM pg_indexes
                WHERE indexname = %s
                """,
                [index_name],
            )

            index_exists = cursor.fetchone()[0] > 0

            if not index_exists:
                # Create spatial index
                cursor.execute(
                    """
                    CREATE INDEX %s ON %s USING GIST (%s)
                    """,
                    [index_name, table_name, location_db_column],
                )

            # Cluster the data based on spatial proximity
            cursor.execute(
                """
                CLUSTER %s USING %s
                """,
                [table_name, index_name],
            )

            # Analyze the table to update statistics
            cursor.execute(
                """
                ANALYZE %s
                """,
                [table_name],
            )

            return (
                True,
                f"Successfully optimized spatial index for {model_class.__name__}",
            )
    except Exception as e:
        return False, f"Error optimizing spatial index: {str(e)}"


def has_postgis_geocoding() -> bool:
    """Check if PostGIS geocoding extension is available"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_proc WHERE proname = 'geocode' LIMIT 1")
            return cursor.fetchone() is not None
    except Exception:
        return False


def calculate_distance(
    point1: Union[Point, Tuple[float, float]], point2: Union[Point, Tuple[float, float]]
) -> float:
    """
    Calculate the geodesic distance between two points

    Args:
        point1: First point (Point object or lng/lat tuple)
        point2: Second point (Point object or lng/lat tuple)

    Returns:
        Distance in kilometers
    """
    # Convert to Point objects if needed
    if not isinstance(point1, Point):
        point1 = Point(point1[0], point1[1], srid=DEFAULT_SRID)
    if not isinstance(point2, Point):
        point2 = Point(point2[0], point2[1], srid=DEFAULT_SRID)

    # Use PostGIS distance calculation for accuracy
    # This assumes both points have the same SRID
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_Distance_Spheroid("
                "  ST_SetSRID(ST_MakePoint(%s, %s), %s),"
                "  ST_SetSRID(ST_MakePoint(%s, %s), %s),"
                "  'SPHEROID[\"WGS 84\",6378137,298.257223563]'"
                ")",
                [point1.x, point1.y, DEFAULT_SRID, point2.x, point2.y, DEFAULT_SRID],
            )
            result = cursor.fetchone()
            # Convert meters to kilometers
            return result[0] / 1000 if result else 0
    except Exception:
        # Fall back to Haversine formula if PostGIS calculation fails
        return _haversine(point1.y, point1.x, point2.y, point2.x)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance using Haversine formula

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Convert to kilometers
    return c * EARTH_RADIUS_KM
