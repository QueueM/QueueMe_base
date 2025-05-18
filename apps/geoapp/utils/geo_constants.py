# Earth radius in various units
EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_MILES = 3958.8
EARTH_RADIUS_METERS = 6371000.0

# Default search radius (in kilometers)
DEFAULT_SEARCH_RADIUS_KM = 5.0

# Maximum search radius limits (to prevent excessive queries)
MAX_SEARCH_RADIUS_KM = 50.0

# City match threshold (km)
CITY_MATCH_THRESHOLD_KM = 10.0

# Average travel speeds (km/h)
TRAVEL_SPEED_WALKING = 5.0
TRAVEL_SPEED_CYCLING = 15.0
TRAVEL_SPEED_DRIVING = 40.0
TRAVEL_SPEED_TRANSIT = 25.0

# Saudi Arabia bounding box
SAUDI_ARABIA_BOUNDS = {
    "min_lat": 16.0,
    "max_lat": 32.0,
    "min_lng": 34.0,
    "max_lng": 56.0,
}

# Major Saudi cities with coordinates
SAUDI_CITIES = {
    "Riyadh": (24.7136, 46.6753),
    "Jeddah": (21.4858, 39.1925),
    "Mecca": (21.3891, 39.8579),
    "Medina": (24.5247, 39.5692),
    "Dammam": (26.4207, 50.0888),
    "Taif": (21.2700, 40.4158),
    "Tabuk": (28.3998, 36.5715),
    "Abha": (18.2164, 42.5053),
    "Khobar": (26.2172, 50.1971),
    "Dhahran": (26.2361, 50.0393),
}

# Default coordinate system SRID (WGS 84)
DEFAULT_SRID = 4326

# Spatial database index type
SPATIAL_INDEX_TYPE = "GIST"
