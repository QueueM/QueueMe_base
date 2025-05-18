"""
Geospatial algorithms for location-based calculations.

This package contains sophisticated algorithms for geospatial calculations,
including distance calculation, travel time estimation, location filtering,
and same-city visibility rules.

Key components:
- distance: Haversine distance calculation between coordinates
- spatial_indexing: R-tree spatial indexing for efficient location queries
- travel_time: Travel time estimation between locations
- geo_visibility: Same-city content visibility algorithm
"""

from .distance import distance_between, distance_matrix
from .geo_visibility import filter_visible_content
from .spatial_indexing import SpatialIndex
from .travel_time import estimate_travel_time

__all__ = [
    "distance_between",
    "distance_matrix",
    "SpatialIndex",
    "estimate_travel_time",
    "filter_visible_content",
]
