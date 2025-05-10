import math

from django.contrib.gis.geos import Point


def validate_coordinates(latitude, longitude):
    """
    Validate if coordinates are within valid ranges

    Args:
        latitude: Latitude (-90 to 90)
        longitude: Longitude (-180 to 180)

    Returns:
        Boolean indicating if coordinates are valid
    """
    try:
        lat = float(latitude)
        lng = float(longitude)

        return -90 <= lat <= 90 and -180 <= lng <= 180
    except (ValueError, TypeError):
        return False


def create_point(latitude, longitude):
    """
    Create a GeoDjango Point object from coordinates

    Args:
        latitude: Latitude value
        longitude: Longitude value

    Returns:
        Point object
    """
    if not validate_coordinates(latitude, longitude):
        raise ValueError("Invalid coordinates")

    return Point(float(longitude), float(latitude), srid=4326)


def format_coordinates(coordinates, format_type="dms"):
    """
    Format coordinates to a specific format

    Args:
        coordinates: Tuple of (latitude, longitude)
        format_type: Format type ('dms' for degrees-minutes-seconds,
                                 'dm' for degrees-decimal minutes,
                                 'dd' for decimal degrees)

    Returns:
        Formatted coordinate string
    """
    latitude, longitude = float(coordinates[0]), float(coordinates[1])

    if format_type == "dms":
        # Degrees, minutes, seconds
        lat_deg = int(latitude)
        lat_min = int((latitude - lat_deg) * 60)
        lat_sec = ((latitude - lat_deg) * 60 - lat_min) * 60

        lng_deg = int(longitude)
        lng_min = int((longitude - lng_deg) * 60)
        lng_sec = ((longitude - lng_deg) * 60 - lng_min) * 60

        lat_dir = "N" if latitude >= 0 else "S"
        lng_dir = "E" if longitude >= 0 else "W"

        return f"{abs(lat_deg)}°{lat_min}'{lat_sec:.2f}\"{lat_dir}, {abs(lng_deg)}°{lng_min}'{lng_sec:.2f}\"{lng_dir}"

    elif format_type == "dm":
        # Degrees, decimal minutes
        lat_deg = int(latitude)
        lat_min = (latitude - lat_deg) * 60

        lng_deg = int(longitude)
        lng_min = (longitude - lng_deg) * 60

        lat_dir = "N" if latitude >= 0 else "S"
        lng_dir = "E" if longitude >= 0 else "W"

        return f"{abs(lat_deg)}°{lat_min:.4f}'{lat_dir}, {abs(lng_deg)}°{lng_min:.4f}'{lng_dir}"

    else:  # format_type == 'dd'
        # Decimal degrees
        return f"{latitude:.6f}, {longitude:.6f}"


def parse_coordinates(coordinate_string):
    """
    Parse coordinates from a string

    Args:
        coordinate_string: String representation of coordinates

    Returns:
        Tuple of (latitude, longitude)
    """
    # Try comma-separated decimal format first (most common)
    try:
        parts = coordinate_string.split(",")
        if len(parts) == 2:
            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())

            if validate_coordinates(latitude, longitude):
                return (latitude, longitude)
    except (ValueError, TypeError):
        pass

    # TODO: Add parsing for DMS format if needed

    raise ValueError("Unable to parse coordinates from string")


def calculate_bounding_box(center_lat, center_lng, radius_km):
    """
    Calculate a bounding box around a center point

    Args:
        center_lat: Center latitude
        center_lng: Center longitude
        radius_km: Radius in kilometers

    Returns:
        Dictionary with min/max lat/lng values
    """
    # Earth's radius in km
    EARTH_RADIUS = 6371.0

    # Convert radius from km to radians
    radius_rad = radius_km / EARTH_RADIUS

    # Convert center coordinates to radians
    center_lat_rad = math.radians(float(center_lat))
    center_lng_rad = math.radians(float(center_lng))

    # Calculate min/max latitudes
    min_lat_rad = center_lat_rad - radius_rad
    max_lat_rad = center_lat_rad + radius_rad

    # Calculate min/max longitudes
    # The delta longitude depends on the latitude
    delta_lng_rad = math.asin(math.sin(radius_rad) / math.cos(center_lat_rad))
    min_lng_rad = center_lng_rad - delta_lng_rad
    max_lng_rad = center_lng_rad + delta_lng_rad

    # Convert back to degrees
    min_lat = math.degrees(min_lat_rad)
    max_lat = math.degrees(max_lat_rad)
    min_lng = math.degrees(min_lng_rad)
    max_lng = math.degrees(max_lng_rad)

    # Handle edge cases at poles and 180th meridian
    min_lat = max(-90.0, min_lat)
    max_lat = min(90.0, max_lat)

    # Handle longitude wrap-around
    if min_lng < -180.0:
        min_lng += 360.0
    if max_lng > 180.0:
        max_lng -= 360.0

    return {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lng": min_lng,
        "max_lng": max_lng,
    }
