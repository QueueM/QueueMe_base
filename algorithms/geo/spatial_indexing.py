"""
R-tree spatial indexing for efficient location queries.

This module provides an optimized R-tree based spatial index implementation for
fast geographical queries such as finding points within a radius or bounding box.
"""

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rtree import index

from .distance import distance_between

logger = logging.getLogger(__name__)


class SpatialIndex:
    """
    R-tree based spatial index for efficient geographic queries.

    This class provides methods for indexing points or shapes and querying them
    efficiently using an R-tree data structure. It's particularly useful for
    nearest-neighbor and radius-based queries that would otherwise require
    checking distances to all points in a collection.
    """

    def __init__(self, properties: Optional[Dict[str, Any]] = None):
        """
        Initialize a spatial index.

        Args:
            properties: Optional dictionary of properties for the underlying R-tree index
        """
        # Set up default properties if none provided
        if properties is None:
            properties = index.Property()
            properties.dimension = 2  # 2D points (lat, lon)
            properties.buffering_capacity = 10  # Tune for performance
            properties.fill_factor = 0.7  # Tune for performance
            properties.leaf_capacity = 100  # Tune for performance
            properties.near_minimum_overlap_factor = 32  # Tune for performance

        # Create the R-tree index
        self.idx = index.Index(properties=properties)

        # Keep track of items for efficient retrieval
        self.items = {}

        # Counter for generating sequential IDs
        self.counter = 0

    def insert(
        self,
        location: Union[Dict[str, float], Tuple[float, float]],
        item_data: Any = None,
        item_id: Optional[int] = None,
    ) -> int:
        """
        Insert a location into the spatial index.

        Args:
            location: Location as either:
                     - dict with 'latitude' and 'longitude' keys, or
                     - tuple of (latitude, longitude)
            item_data: Associated data to store with this location
            item_id: Optional ID for the item. If not provided, an ID is generated.

        Returns:
            ID of the inserted item
        """
        # Extract coordinates
        if isinstance(location, dict):
            lat = location.get("latitude") or location.get("lat")
            lon = location.get("longitude") or location.get("lng") or location.get("lon")
        else:
            lat, lon = location

        # Generate ID if not provided
        if item_id is None:
            item_id = self.counter
            self.counter += 1

        # Create a small bounding box around the point
        # This converts the point to a tiny rectangle for the R-tree
        # Using a small epsilon value to create a non-zero area rectangle
        epsilon = 0.0000001
        bbox = (lon - epsilon, lat - epsilon, lon + epsilon, lat + epsilon)

        # Insert into the R-tree index
        self.idx.insert(item_id, bbox)

        # Store the item data and coordinates for retrieval
        self.items[item_id] = {"coordinates": (lat, lon), "data": item_data}

        return item_id

    def bulk_insert(
        self,
        locations: List[Union[Dict[str, float], Tuple[float, float]]],
        items_data: Optional[List[Any]] = None,
        start_id: int = 0,
    ) -> List[int]:
        """
        Insert multiple locations in bulk for better performance.

        Args:
            locations: List of locations to insert
            items_data: Optional list of associated data items (must match length of locations)
            start_id: Starting ID for the items

        Returns:
            List of IDs for the inserted items
        """
        if items_data is not None and len(items_data) != len(locations):
            raise ValueError("items_data must have the same length as locations")

        # Generate stream of (id, bbox, None) tuples for bulk insertion
        def generate_items():
            for i, location in enumerate(locations):
                # Extract coordinates
                if isinstance(location, dict):
                    lat = location.get("latitude") or location.get("lat")
                    lon = location.get("longitude") or location.get("lng") or location.get("lon")
                else:
                    lat, lon = location

                # Create tiny bounding box
                epsilon = 0.0000001
                bbox = (lon - epsilon, lat - epsilon, lon + epsilon, lat + epsilon)

                # Generate ID
                item_id = start_id + i

                # Store in items dict
                self.items[item_id] = {
                    "coordinates": (lat, lon),
                    "data": None if items_data is None else items_data[i],
                }

                # Yield for R-tree bulk insert
                yield (item_id, bbox, None)

        # Bulk insert
        self.idx.bulk_insert(generate_items())

        # Update counter
        self.counter = max(self.counter, start_id + len(locations))

        # Return list of IDs
        return list(range(start_id, start_id + len(locations)))

    def delete(self, item_id: int) -> bool:
        """
        Delete an item from the spatial index.

        Args:
            item_id: ID of the item to delete

        Returns:
            True if item was found and deleted, False otherwise
        """
        if item_id not in self.items:
            return False

        # Get coordinates
        lat, lon = self.items[item_id]["coordinates"]

        # Recreate the bounding box
        epsilon = 0.0000001
        bbox = (lon - epsilon, lat - epsilon, lon + epsilon, lat + epsilon)

        # Delete from R-tree
        self.idx.delete(item_id, bbox)

        # Delete from items dictionary
        del self.items[item_id]

        return True

    def update(
        self,
        item_id: int,
        new_location: Union[Dict[str, float], Tuple[float, float]],
        new_data: Optional[Any] = None,
    ) -> bool:
        """
        Update an item's location and optionally its data.

        Args:
            item_id: ID of the item to update
            new_location: New location for the item
            new_data: Optional new data to associate with the item

        Returns:
            True if item was found and updated, False otherwise
        """
        if item_id not in self.items:
            return False

        # Delete old entry
        old_lat, old_lon = self.items[item_id]["coordinates"]
        epsilon = 0.0000001
        old_bbox = (
            old_lon - epsilon,
            old_lat - epsilon,
            old_lon + epsilon,
            old_lat + epsilon,
        )
        self.idx.delete(item_id, old_bbox)

        # Extract new coordinates
        if isinstance(new_location, dict):
            new_lat = new_location.get("latitude") or new_location.get("lat")
            new_lon = (
                new_location.get("longitude") or new_location.get("lng") or new_location.get("lon")
            )
        else:
            new_lat, new_lon = new_location

        # Create new bounding box
        new_bbox = (
            new_lon - epsilon,
            new_lat - epsilon,
            new_lon + epsilon,
            new_lat + epsilon,
        )

        # Insert with new location
        self.idx.insert(item_id, new_bbox)

        # Update items dictionary
        self.items[item_id]["coordinates"] = (new_lat, new_lon)

        # Update data if provided
        if new_data is not None:
            self.items[item_id]["data"] = new_data

        return True

    def nearest(
        self,
        location: Union[Dict[str, float], Tuple[float, float]],
        num_results: int = 1,
        max_distance: Optional[float] = None,
        distance_in_miles: bool = False,
    ) -> List[Tuple[int, float, Any]]:
        """
        Find the nearest items to a location.

        Args:
            location: Query location
            num_results: Maximum number of results to return
            max_distance: Optional maximum distance in km (or miles if distance_in_miles=True)
            distance_in_miles: If True, interpret max_distance in miles and return distances in miles

        Returns:
            List of tuples (item_id, distance, item_data) sorted by distance
        """
        # Extract coordinates
        if isinstance(location, dict):
            lat = location.get("latitude") or location.get("lat")
            lon = location.get("longitude") or location.get("lng") or location.get("lon")
        else:
            lat, lon = location

        # Query point
        query_point = (lat, lon)

        # First, get more candidates than needed using R-tree nearest query
        # This is much faster than checking all points
        nearest_candidates = list(
            self.idx.nearest(
                (lon, lat, lon, lat),  # Query rectangle (a point)
                num_results * 2,  # Get more candidates than needed to account for filtering
            )
        )

        # Calculate actual distances and filter
        results = []
        for item_id in nearest_candidates:
            if item_id in self.items:  # Ensure item still exists
                item_coords = self.items[item_id]["coordinates"]
                distance = distance_between(query_point, item_coords, distance_in_miles)

                # Filter by max_distance if provided
                if max_distance is not None and distance > max_distance:
                    continue

                item_data = self.items[item_id]["data"]
                results.append((item_id, distance, item_data))

        # Sort by distance and limit to num_results
        results.sort(key=lambda x: x[1])
        return results[:num_results]

    def within_radius(
        self,
        center: Union[Dict[str, float], Tuple[float, float]],
        radius: float,
        radius_in_miles: bool = False,
        max_results: Optional[int] = None,
    ) -> List[Tuple[int, float, Any]]:
        """
        Find all items within a radius of a center point.

        Args:
            center: Center location
            radius: Radius to search within (in km, or miles if radius_in_miles=True)
            radius_in_miles: If True, interpret radius in miles and return distances in miles
            max_results: Optional maximum number of results to return

        Returns:
            List of tuples (item_id, distance, item_data) sorted by distance
        """
        # Extract coordinates
        if isinstance(center, dict):
            lat = center.get("latitude") or center.get("lat")
            lon = center.get("longitude") or center.get("lng") or center.get("lon")
        else:
            lat, lon = center

        # Calculate a bounding box that contains the circle
        # Convert radius to degrees (approximate)
        if radius_in_miles:
            radius_km = radius * 1.60934  # Miles to km
        else:
            radius_km = radius

        # Approximate conversion from km to degrees
        # 1 degree of latitude is approximately 111 km
        radius_deg_lat = radius_km / 111.0

        # 1 degree of longitude varies with latitude
        # cos(lat) factor accounts for this variance
        radius_deg_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

        # Create bounding box
        min_lon = lon - radius_deg_lon
        min_lat = lat - radius_deg_lat
        max_lon = lon + radius_deg_lon
        max_lat = lat + radius_deg_lat

        # Query the R-tree for items in the bounding box
        bbox_results = list(self.idx.intersection((min_lon, min_lat, max_lon, max_lat)))

        # Filter results by exact distance and add item data
        center_point = (lat, lon)
        results = []

        for item_id in bbox_results:
            if item_id in self.items:  # Ensure item still exists
                item_coords = self.items[item_id]["coordinates"]
                distance = distance_between(center_point, item_coords, radius_in_miles)

                # Only include if within exact radius
                if distance <= radius:
                    item_data = self.items[item_id]["data"]
                    results.append((item_id, distance, item_data))

        # Sort by distance
        results.sort(key=lambda x: x[1])

        # Limit results if requested
        if max_results is not None:
            results = results[:max_results]

        return results

    def custom_filter(
        self,
        filter_func: Callable[[Tuple[float, float], Any], bool],
        bounding_box: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[Tuple[int, Tuple[float, float], Any]]:
        """
        Filter items using a custom function.

        Args:
            filter_func: Function that takes (coordinates, item_data) and returns bool
            bounding_box: Optional bounding box to pre-filter (min_lon, min_lat, max_lon, max_lat)

        Returns:
            List of tuples (item_id, coordinates, item_data) for items that pass the filter
        """
        # If bounding box provided, pre-filter using R-tree
        if bounding_box:
            item_ids = list(self.idx.intersection(bounding_box))
        else:
            item_ids = list(self.items.keys())

        # Apply custom filter
        results = []
        for item_id in item_ids:
            if item_id in self.items:  # Ensure item still exists
                coords = self.items[item_id]["coordinates"]
                data = self.items[item_id]["data"]

                if filter_func(coords, data):
                    results.append((item_id, coords, data))

        return results

    def size(self) -> int:
        """
        Get the number of items in the index.

        Returns:
            Number of items in the index
        """
        return len(self.items)

    def clear(self) -> None:
        """Clear all items from the index."""
        self.idx = index.Index(properties=self.idx.properties)
        self.items = {}
        self.counter = 0
