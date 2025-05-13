"""
Same-city content visibility algorithm.

This module implements the "same city" visibility rule, which ensures that content
(shops, reels, etc.) is only visible to customers in the same city, with supplementary
distance-based filtering and sorting.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .distance import distance_between

logger = logging.getLogger(__name__)


def is_in_same_city(customer_location: Dict[str, Any], content_location: Dict[str, Any]) -> bool:
    """
    Determine if a customer and content are in the same city.

    Args:
        customer_location: Dict with at least 'city' key
        content_location: Dict with at least 'city' key

    Returns:
        True if they are in the same city, False otherwise
    """
    # Simple exact match on city name
    customer_city = customer_location.get("city", "").lower()
    content_city = content_location.get("city", "").lower()

    return customer_city == content_city


def is_in_same_region(customer_location: Dict[str, Any], content_location: Dict[str, Any]) -> bool:
    """
    Determine if a customer and content are in the same broader region.

    Args:
        customer_location: Dict with location info (city, region, etc.)
        content_location: Dict with location info (city, region, etc.)

    Returns:
        True if they are in the same region, False otherwise
    """
    # Check if same city first (fastest check)
    if is_in_same_city(customer_location, content_location):
        return True

    # If not same city, check region/state/province
    customer_region = customer_location.get("region", "").lower()
    content_region = content_location.get("region", "").lower()

    return customer_region == content_region and customer_region != ""


def filter_visible_content(
    customer_location: Dict[str, Any],
    content_items: List[Dict[str, Any]],
    location_key: str = "location",
    city_key: str = "city",
    strict_city_match: bool = True,
    max_distance_km: Optional[float] = None,
    sort_by_distance: bool = False,
    include_distance: bool = False,
) -> List[Dict[str, Any]]:
    """
    Filter content items based on visibility rules.

    Args:
        customer_location: Customer's location info with city and optional coordinates
        content_items: List of content items to filter
        location_key: Key to access location data in content items
        city_key: Key to access city within location data
        strict_city_match: If True, require exact city match; if False, allow same region
        max_distance_km: Optional maximum distance in kilometers
        sort_by_distance: If True, sort results by distance (nearest first)
        include_distance: If True, add distance information to results

    Returns:
        Filtered (and optionally sorted) list of content items
    """
    filtered_items = []
    customer_city = customer_location.get(city_key, "").lower()

    # Get customer coordinates if available
    customer_coords = None
    if "latitude" in customer_location and "longitude" in customer_location:
        customer_coords = {
            "latitude": customer_location["latitude"],
            "longitude": customer_location["longitude"],
        }

    for item in content_items:
        # Get content location
        content_location = item.get(location_key, {})
        content_city = content_location.get(city_key, "").lower()

        # Skip if cities don't match and strict matching is required
        if strict_city_match and content_city != customer_city:
            continue

        # If not strict matching, check region match
        if not strict_city_match and not is_in_same_region(customer_location, content_location):
            continue

        # Check distance constraint if coordinates are available and max_distance is set
        if max_distance_km is not None and customer_coords is not None:
            # Get content coordinates
            content_coords = None
            if "latitude" in content_location and "longitude" in content_location:
                content_coords = {
                    "latitude": content_location["latitude"],
                    "longitude": content_location["longitude"],
                }

            # Skip if coordinates missing
            if content_coords is None:
                continue

            # Calculate distance
            distance = distance_between(customer_coords, content_coords)

            # Skip if too far
            if distance > max_distance_km:
                continue

            # Add distance info if requested
            if include_distance:
                item_copy = item.copy()
                item_copy["distance_km"] = round(distance, 2)
                filtered_items.append(item_copy)
            else:
                filtered_items.append(item)
        else:
            # No distance check required
            filtered_items.append(item)

    # Sort by distance if requested and coordinates are available
    if sort_by_distance and customer_coords is not None:
        # Calculate distances if not already included
        if not include_distance:
            for item in filtered_items:
                content_location = item.get(location_key, {})
                if "latitude" in content_location and "longitude" in content_location:
                    content_coords = {
                        "latitude": content_location["latitude"],
                        "longitude": content_location["longitude"],
                    }
                    item["distance_km"] = distance_between(customer_coords, content_coords)
                else:
                    # Default to a large distance if coordinates not available
                    item["distance_km"] = float("inf")

        # Sort by distance
        filtered_items.sort(key=lambda x: x.get("distance_km", float("inf")))

        # Remove distance info if it wasn't requested
        if not include_distance:
            for item in filtered_items:
                if "distance_km" in item:
                    del item["distance_km"]

    return filtered_items


def get_nearby_cities(
    city: str,
    city_data: List[Dict[str, Any]],
    max_distance_km: float = 50.0,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find cities that are near a given city.

    Args:
        city: Name of the city to find nearby cities for
        city_data: List of city dictionaries with name and coordinates
        max_distance_km: Maximum distance in kilometers to consider as "nearby"
        max_results: Maximum number of nearby cities to return

    Returns:
        List of nearby city dictionaries with distance info added
    """
    # Find the target city
    target_city_data = None
    for city_info in city_data:
        if city_info.get("name", "").lower() == city.lower():
            target_city_data = city_info
            break

    if not target_city_data:
        logger.warning(f"City '{city}' not found in city data")
        return []

    # Extract target coordinates
    target_coords = {
        "latitude": target_city_data.get("latitude"),
        "longitude": target_city_data.get("longitude"),
    }

    # Find nearby cities
    nearby_cities = []
    for city_info in city_data:
        # Skip the target city itself
        if city_info.get("name", "").lower() == city.lower():
            continue

        # Extract coordinates
        city_coords = {
            "latitude": city_info.get("latitude"),
            "longitude": city_info.get("longitude"),
        }

        # Calculate distance
        distance = distance_between(target_coords, city_coords)

        # Add to results if within max distance
        if distance <= max_distance_km:
            city_copy = city_info.copy()
            city_copy["distance_km"] = round(distance, 2)
            nearby_cities.append(city_copy)

    # Sort by distance and limit to max_results
    nearby_cities.sort(key=lambda x: x.get("distance_km", float("inf")))
    return nearby_cities[:max_results]


def generate_geofence(
    center: Union[Dict[str, float], Tuple[float, float]],
    radius_km: float,
    points: int = 16,
) -> List[Dict[str, float]]:
    """
    Generate a geofence (polygon) around a center point.

    Args:
        center: Center point of the geofence
        radius_km: Radius in kilometers
        points: Number of points to use for the polygon

    Returns:
        List of coordinate dictionaries forming a polygon
    """
    import math

    # Extract center coordinates
    if isinstance(center, dict):
        center_lat = center.get("latitude") or center.get("lat")
        center_lon = center.get("longitude") or center.get("lng") or center.get("lon")
    else:
        center_lat, center_lon = center

    # Earth's radius in km
    earth_radius = 6371.0

    # Convert radius from km to radians
    radius_rad = radius_km / earth_radius

    # Generate points around the circle
    polygon = []
    for i in range(points):
        # Calculate angle for this point
        angle = (2 * math.pi * i) / points

        # Calculate offset from center
        dx = radius_rad * math.cos(angle)
        dy = radius_rad * math.sin(angle)

        # Convert to lat/lon
        # Note: This is an approximation that works well for small distances
        lat = center_lat + (dy * 180 / math.pi)
        lon = center_lon + (dx * 180 / math.pi) / math.cos(center_lat * math.pi / 180)

        polygon.append({"latitude": lat, "longitude": lon})

    # Close the polygon by adding the first point again
    polygon.append(polygon[0])

    return polygon


def is_point_in_polygon(
    point: Union[Dict[str, float], Tuple[float, float]],
    polygon: List[Union[Dict[str, float], Tuple[float, float]]],
) -> bool:
    """
    Determine if a point is inside a polygon using the ray casting algorithm.

    Args:
        point: Point to check
        polygon: List of points forming a polygon

    Returns:
        True if the point is inside the polygon, False otherwise
    """
    # Extract point coordinates
    if isinstance(point, dict):
        x = point.get("longitude") or point.get("lng") or point.get("lon")
        y = point.get("latitude") or point.get("lat")
    else:
        x, y = point[1], point[0]  # lon, lat

    # Extract polygon coordinates
    poly_points = []
    for p in polygon:
        if isinstance(p, dict):
            px = p.get("longitude") or p.get("lng") or p.get("lon")
            py = p.get("latitude") or p.get("lat")
            poly_points.append((px, py))
        else:
            poly_points.append((p[1], p[0]))  # lon, lat

    # Ray casting algorithm
    inside = False
    n = len(poly_points)

    p1x, p1y = poly_points[0]
    for i in range(1, n + 1):
        p2x, p2y = poly_points[i % n]

        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x

                    if p1x == p2x or x <= x_intersection:
                        inside = not inside

        p1x, p1y = p2x, p2y

    return inside
