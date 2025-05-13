"""
Haversine distance calculation between geographic coordinates.

This module provides functions for calculating distances between geographical
points using the Haversine formula, which accounts for the Earth's curvature.
"""

import math
from typing import Dict, List, Tuple, Union

import numpy as np

# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth using the Haversine formula.

    Args:
        lat1: Latitude of point 1 (in degrees)
        lon1: Longitude of point 1 (in degrees)
        lat2: Latitude of point 2 (in degrees)
        lon2: Longitude of point 2 (in degrees)

    Returns:
        Distance in kilometers between the two points
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c


def distance_between(
    point1: Union[Dict[str, float], Tuple[float, float]],
    point2: Union[Dict[str, float], Tuple[float, float]],
    return_miles: bool = False,
) -> float:
    """
    Calculate the distance between two geographic points.

    Args:
        point1: First point as either:
               - dict with 'latitude' and 'longitude' keys, or
               - tuple of (latitude, longitude)
        point2: Second point in same format as point1
        return_miles: If True, return the distance in miles; otherwise in kilometers

    Returns:
        Distance between the points in kilometers or miles
    """
    # Extract coordinates from point1
    if isinstance(point1, dict):
        lat1 = point1.get("latitude") or point1.get("lat")
        lon1 = point1.get("longitude") or point1.get("lng") or point1.get("lon")
    else:
        lat1, lon1 = point1

    # Extract coordinates from point2
    if isinstance(point2, dict):
        lat2 = point2.get("latitude") or point2.get("lat")
        lon2 = point2.get("longitude") or point2.get("lng") or point2.get("lon")
    else:
        lat2, lon2 = point2

    # Calculate distance in kilometers
    distance_km = haversine(lat1, lon1, lat2, lon2)

    # Convert to miles if requested
    if return_miles:
        return distance_km * 0.621371  # km to miles conversion

    return distance_km


def distance_matrix(
    points: List[Union[Dict[str, float], Tuple[float, float]]],
    return_miles: bool = False,
) -> np.ndarray:
    """
    Calculate a matrix of distances between multiple geographic points.

    Args:
        points: List of points, each as either:
               - dict with 'latitude' and 'longitude' keys, or
               - tuple of (latitude, longitude)
        return_miles: If True, return distances in miles; otherwise in kilometers

    Returns:
        NumPy array of distances where distance_matrix[i][j] is the distance
        between points[i] and points[j]
    """
    n = len(points)

    # Initialize a square matrix of zeros
    matrix = np.zeros((n, n))

    # Calculate distances between all pairs of points
    for i in range(n):
        for j in range(i + 1, n):  # Only calculate upper triangle
            dist = distance_between(points[i], points[j], return_miles)
            # Fill both upper and lower triangle (symmetric matrix)
            matrix[i, j] = dist
            matrix[j, i] = dist

    return matrix


def find_nearest_point(
    target: Union[Dict[str, float], Tuple[float, float]],
    points: List[Union[Dict[str, float], Tuple[float, float]]],
    return_miles: bool = False,
) -> Tuple[int, float]:
    """
    Find the nearest point to a target from a list of points.

    Args:
        target: Target point as either:
               - dict with 'latitude' and 'longitude' keys, or
               - tuple of (latitude, longitude)
        points: List of points to search
        return_miles: If True, calculate distances in miles; otherwise in kilometers

    Returns:
        Tuple of (index of nearest point, distance to that point)
    """
    if not points:
        raise ValueError("Points list cannot be empty")

    min_dist = float("inf")
    min_idx = -1

    for i, point in enumerate(points):
        dist = distance_between(target, point, return_miles)
        if dist < min_dist:
            min_dist = dist
            min_idx = i

    return min_idx, min_dist


def find_points_within_radius(
    center: Union[Dict[str, float], Tuple[float, float]],
    points: List[Union[Dict[str, float], Tuple[float, float]]],
    radius: float,
    in_miles: bool = False,
) -> List[Tuple[int, float]]:
    """
    Find all points within a given radius of a center point.

    Args:
        center: Center point as either:
               - dict with 'latitude' and 'longitude' keys, or
               - tuple of (latitude, longitude)
        points: List of points to search
        radius: Radius to search within
        in_miles: If True, radius and distances are in miles; otherwise in kilometers

    Returns:
        List of tuples (index of point, distance), sorted by distance
    """
    results = []

    for i, point in enumerate(points):
        dist = distance_between(center, point, in_miles)
        if dist <= radius:
            results.append((i, dist))

    # Sort results by distance
    results.sort(key=lambda x: x[1])

    return results


def centroid(
    points: List[Union[Dict[str, float], Tuple[float, float]]],
) -> Tuple[float, float]:
    """
    Calculate the geographic centroid of a set of points.
    Note: This is a simple averaging approach that works reasonably well
    for points that are close together.

    Args:
        points: List of geographic points

    Returns:
        Tuple of (latitude, longitude) for the centroid
    """
    if not points:
        raise ValueError("Points list cannot be empty")

    # Convert points to (lat, lon) tuples
    coords = []
    for point in points:
        if isinstance(point, dict):
            lat = point.get("latitude") or point.get("lat")
            lon = point.get("longitude") or point.get("lng") or point.get("lon")
            coords.append((lat, lon))
        else:
            coords.append(point)

    # Simple arithmetic mean - adequate for small areas
    sum_lat = sum(lat for lat, _ in coords)
    sum_lon = sum(lon for _, lon in coords)

    avg_lat = sum_lat / len(coords)
    avg_lon = sum_lon / len(coords)

    return (avg_lat, avg_lon)
