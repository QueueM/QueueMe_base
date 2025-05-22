"""
Location-based Content Filter

Service for dynamically filtering content based on user location data,
using geospatial queries and configurable filtering rules.
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.customersapp.models import Customer
from apps.geoapp.models import City
from apps.reelsapp.models import Reel
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story

logger = logging.getLogger(__name__)


class LocationContentFilter:
    """
    Filter for content based on geographic location, with advanced
    features like dynamic radius, relevance scoring, and geo-targeted content.
    """

    # Default settings
    DEFAULT_RADIUS_KM = 10  # Default search radius in kilometers
    DEFAULT_MAX_RESULTS = 100  # Default maximum results to return
    DEFAULT_CACHE_TTL = 60 * 10  # 10 minutes
    MAJOR_CITIES_RANGE_KM = 50  # Range for major cities in kilometers

    def __init__(
        self, user_location: Optional[Point] = None, user_id: Optional[str] = None
    ):
        """
        Initialize the location filter with user location

        Args:
            user_location: Optional user location as Point
            user_id: Optional user ID to load location from profile
        """
        self.user_location = user_location
        self.user_id = user_id
        self.radius_km = self.DEFAULT_RADIUS_KM
        self.max_results = self.DEFAULT_MAX_RESULTS
        self.apply_relevance_score = True
        self.country_id = None
        self.city_id = None
        self.region_id = None

        # Load user location if provided user_id but no location
        if not user_location and user_id:
            self._load_user_location()

    def set_radius(self, radius_km: float) -> "LocationContentFilter":
        """
        Set the search radius in kilometers

        Args:
            radius_km: Search radius in kilometers

        Returns:
            Self for method chaining
        """
        self.radius_km = radius_km
        return self

    def set_max_results(self, max_results: int) -> "LocationContentFilter":
        """
        Set the maximum number of results to return

        Args:
            max_results: Maximum number of results

        Returns:
            Self for method chaining
        """
        self.max_results = max_results
        return self

    def set_location(
        self, latitude: float, longitude: float
    ) -> "LocationContentFilter":
        """
        Set the user location

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Self for method chaining
        """
        self.user_location = Point(longitude, latitude, srid=4326)

        # Clear region information to be recalculated
        self.country_id = None
        self.city_id = None
        self.region_id = None

        return self

    def set_city(self, city_id: str) -> "LocationContentFilter":
        """
        Set the city for filtering

        Args:
            city_id: City ID to filter by

        Returns:
            Self for method chaining
        """
        self.city_id = city_id

        # If we don't have user location, try to set to city center
        if not self.user_location:
            try:
                city = City.objects.get(id=city_id)
                if city.location:
                    self.user_location = city.location
            except City.DoesNotExist:
                pass

        return self

    def disable_relevance_scoring(self) -> "LocationContentFilter":
        """
        Disable relevance scoring based on distance

        Returns:
            Self for method chaining
        """
        self.apply_relevance_score = False
        return self

    def filter_shops(self, query=None) -> List[Dict[str, Any]]:
        """
        Filter shops by location

        Args:
            query: Optional base query to filter on

        Returns:
            List of shops with distance information
        """
        # Validate location data
        self._ensure_location()

        # Start with base query or all active shops
        if query is None:
            query = Shop.objects.filter(is_active=True)

        # Apply location filters
        shops = self._apply_location_filters(query)

        # Get the results with distance information
        results = self._format_shop_results(shops)

        return results

    def filter_reels(self, query=None) -> List[Dict[str, Any]]:
        """
        Filter reels by location

        Args:
            query: Optional base query to filter on

        Returns:
            List of reels with location information
        """
        # Validate location data
        self._ensure_location()

        # Start with base query or all active reels
        if query is None:
            query = Reel.objects.filter(is_active=True)

        # Apply location filters to shops associated with reels
        reels = self._apply_location_filters_to_reels(query)

        # Get the results with distance information
        results = self._format_reel_results(reels)

        return results

    def filter_stories(self, query=None) -> List[Dict[str, Any]]:
        """
        Filter stories by location

        Args:
            query: Optional base query to filter on

        Returns:
            List of stories with location information
        """
        # Similar approach to reels
        # Validate location data
        self._ensure_location()

        # Start with base query or all active stories
        if query is None:
            query = Story.objects.filter(is_active=True)

        # Apply location filters to shops associated with stories
        stories = self._apply_location_filters_to_stories(query)

        # Get the results with distance information
        results = self._format_story_results(stories)

        return results

    def filter_services(self, query=None) -> List[Dict[str, Any]]:
        """
        Filter services by location

        Args:
            query: Optional base query to filter on

        Returns:
            List of services with location information
        """
        # Validate location data
        self._ensure_location()

        # Start with base query or all active services
        if query is None:
            query = Service.objects.filter(is_active=True)

        # Apply location filters to shops offering these services
        services = self._apply_location_filters_to_services(query)

        # Get the results with distance information
        results = self._format_service_results(services)

        return results

    def get_nearby_cities(self) -> List[Dict[str, Any]]:
        """
        Get nearby cities based on user location

        Returns:
            List of nearby cities with distance information
        """
        # Validate location data
        self._ensure_location()

        # Cache key based on location and radius
        cache_key = f"nearby_cities:{self.user_location.x:.4f},{self.user_location.y:.4f}:{self.radius_km}"
        cached_result = cache.get(cache_key)

        if cached_result:
            return cached_result

        # Query cities within radius
        cities = (
            City.objects.filter(
                location__dwithin=(self.user_location, D(km=self.radius_km))
            )
            .annotate(distance=Distance("location", self.user_location))
            .order_by("distance")
        )

        # Format results
        results = []
        for city in cities:
            results.append(
                {
                    "id": city.id,
                    "name": city.name,
                    "country": city.country.name if city.country else None,
                    "distance_km": city.distance.km,
                    "location": (
                        {"latitude": city.location.y, "longitude": city.location.x}
                        if city.location
                        else None
                    ),
                }
            )

        # Cache the result
        cache.set(cache_key, results, self.DEFAULT_CACHE_TTL)

        return results

    def get_popular_locations(self) -> List[Dict[str, Any]]:
        """
        Get popular locations near user

        Returns:
            List of popular locations
        """
        # First get current city or nearby cities
        if self.city_id:
            city = City.objects.get(id=self.city_id)
            current_city = {
                "id": city.id,
                "name": city.name,
                "country": city.country.name if city.country else None,
                "location": (
                    {"latitude": city.location.y, "longitude": city.location.x}
                    if city.location
                    else None
                ),
            }
            nearby_cities = [current_city]
        else:
            nearby_cities = self.get_nearby_cities()

        # Get city IDs
        city_ids = [city["id"] for city in nearby_cities]

        # Find popular locations (shops with most customers/views) in these cities
        popular_shops = Shop.objects.filter(
            location__city_id__in=city_ids, is_active=True
        ).order_by("-view_count")[:20]

        # Format results
        results = []
        for shop in popular_shops:
            if not shop.location:
                continue

            results.append(
                {
                    "id": shop.id,
                    "name": shop.name,
                    "type": "shop",
                    "popularity_score": shop.view_count,
                    "location": {
                        "latitude": (
                            shop.location.location.y
                            if hasattr(shop.location, "location")
                            and shop.location.location
                            else None
                        ),
                        "longitude": (
                            shop.location.location.x
                            if hasattr(shop.location, "location")
                            and shop.location.location
                            else None
                        ),
                    },
                }
            )

        return results

    def create_geofence(
        self,
        name: str,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        entity_id: str,
        entity_type: str,
        active_from: Optional[datetime] = None,
        active_until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a geofence for location-based triggers

        Args:
            name: Name of the geofence
            center_lat: Center latitude
            center_lng: Center longitude
            radius_km: Radius in kilometers
            entity_id: ID of entity (shop, promotion, etc.)
            entity_type: Type of entity
            active_from: Start time for geofence
            active_until: End time for geofence

        Returns:
            Created geofence data
        """
        try:
            from apps.geoapp.models import Geofence

            # Create geofence
            geofence = Geofence.objects.create(
                name=name,
                center=Point(center_lng, center_lat, srid=4326),
                radius_km=radius_km,
                entity_id=entity_id,
                entity_type=entity_type,
                active_from=active_from or timezone.now(),
                active_until=active_until,
                is_active=True,
            )

            return {
                "id": geofence.id,
                "name": geofence.name,
                "center": {"latitude": center_lat, "longitude": center_lng},
                "radius_km": radius_km,
                "created_at": geofence.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating geofence: {e}")
            raise

    def check_user_in_geofences(self) -> List[Dict[str, Any]]:
        """
        Check if user is within any active geofences

        Returns:
            List of geofences user is currently in
        """
        if not self.user_location:
            return []

        try:
            from apps.geoapp.models import Geofence

            # Get active geofences
            now = timezone.now()
            geofences = Geofence.objects.filter(
                is_active=True, active_from__lte=now
            ).filter(Q(active_until__isnull=True) | Q(active_until__gt=now))

            # Filter by location (within radius)
            matching_geofences = []

            for geofence in geofences:
                # Calculate distance
                distance_meters = (
                    self.user_location.distance(geofence.center) * 100 * 1000
                )  # Convert to meters

                if distance_meters <= geofence.radius_km * 1000:
                    matching_geofences.append(
                        {
                            "id": geofence.id,
                            "name": geofence.name,
                            "entity_id": geofence.entity_id,
                            "entity_type": geofence.entity_type,
                            "distance_meters": int(distance_meters),
                        }
                    )

            return matching_geofences

        except Exception as e:
            logger.error(f"Error checking geofences: {e}")
            return []

    def _ensure_location(self):
        """Ensure we have location data to work with"""
        if not self.user_location and not self.city_id:
            raise ValueError("Either user location or city must be specified")

        # If we have location but no region data, try to determine it
        if self.user_location and not (
            self.country_id or self.city_id or self.region_id
        ):
            self._determine_region()

    def _load_user_location(self):
        """Load user location from customer profile"""
        if not self.user_id:
            return

        try:
            customer = Customer.objects.get(id=self.user_id)

            # If customer has location coordinates
            if customer.latitude and customer.longitude:
                self.user_location = Point(
                    customer.longitude, customer.latitude, srid=4326
                )

            # If customer has city but no coordinates
            elif customer.city_id and not self.user_location:
                self.city_id = customer.city_id

                # Try to get city center
                city = City.objects.get(id=customer.city_id)
                if city.location:
                    self.user_location = city.location

        except Customer.DoesNotExist:
            logger.warning(f"Customer {self.user_id} not found")

        except Exception as e:
            logger.error(f"Error loading user location: {e}")

    def _determine_region(self):
        """Determine country, region, and city from coordinates"""
        if not self.user_location:
            return

        # Check if we have this in cache
        cache_key = (
            f"location_region:{self.user_location.x:.4f},{self.user_location.y:.4f}"
        )
        cached_data = cache.get(cache_key)

        if cached_data:
            self.country_id = cached_data.get("country_id")
            self.region_id = cached_data.get("region_id")
            self.city_id = cached_data.get("city_id")
            return

        try:
            # Find closest city
            closest_city = (
                City.objects.annotate(distance=Distance("location", self.user_location))
                .order_by("distance")
                .first()
            )

            if closest_city:
                self.city_id = closest_city.id

                if closest_city.region_id:
                    self.region_id = closest_city.region_id

                if closest_city.country_id:
                    self.country_id = closest_city.country_id

                # Cache this result
                cache.set(
                    cache_key,
                    {
                        "country_id": self.country_id,
                        "region_id": self.region_id,
                        "city_id": self.city_id,
                    },
                    60 * 60 * 24,
                )  # 24-hour cache

        except Exception as e:
            logger.error(f"Error determining region: {e}")

    def _apply_location_filters(self, query):
        """
        Apply location filters to a shop query

        Args:
            query: Base query to filter

        Returns:
            Filtered query with distance annotation
        """
        # Start with the base query
        filtered_query = query

        # If we have user coordinates, filter by distance
        if self.user_location:
            filtered_query = (
                filtered_query.filter(
                    location__location__dwithin=(
                        self.user_location,
                        D(km=self.radius_km),
                    )
                )
                .annotate(distance=Distance("location__location", self.user_location))
                .order_by("distance")
            )

        # If we have city but no coordinates, filter by city
        elif self.city_id:
            filtered_query = filtered_query.filter(location__city_id=self.city_id)

        # Apply region filter if specified
        elif self.region_id:
            filtered_query = filtered_query.filter(location__region_id=self.region_id)

        # Apply country filter if specified
        elif self.country_id:
            filtered_query = filtered_query.filter(location__country_id=self.country_id)

        # Apply result limit
        return filtered_query[: self.max_results]

    def _apply_location_filters_to_reels(self, query):
        """
        Apply location filters to a reel query

        Args:
            query: Base query to filter

        Returns:
            Filtered query with distance annotation
        """
        # Start with the base query
        filtered_query = query

        # If we have user coordinates, filter by shop distance
        if self.user_location:
            filtered_query = (
                filtered_query.filter(
                    shop__location__location__dwithin=(
                        self.user_location,
                        D(km=self.radius_km),
                    )
                )
                .annotate(
                    distance=Distance("shop__location__location", self.user_location)
                )
                .order_by("distance")
            )

        # If we have city but no coordinates, filter by city
        elif self.city_id:
            filtered_query = filtered_query.filter(shop__location__city_id=self.city_id)

        # Apply region filter if specified
        elif self.region_id:
            filtered_query = filtered_query.filter(
                shop__location__region_id=self.region_id
            )

        # Apply country filter if specified
        elif self.country_id:
            filtered_query = filtered_query.filter(
                shop__location__country_id=self.country_id
            )

        # Apply result limit
        return filtered_query[: self.max_results]

    def _apply_location_filters_to_stories(self, query):
        """Apply location filters to a story query"""
        # Similar to reels
        # Start with the base query
        filtered_query = query

        # If we have user coordinates, filter by shop distance
        if self.user_location:
            filtered_query = (
                filtered_query.filter(
                    shop__location__location__dwithin=(
                        self.user_location,
                        D(km=self.radius_km),
                    )
                )
                .annotate(
                    distance=Distance("shop__location__location", self.user_location)
                )
                .order_by("distance")
            )

        # If we have city but no coordinates, filter by city
        elif self.city_id:
            filtered_query = filtered_query.filter(shop__location__city_id=self.city_id)

        # Apply region filter if specified
        elif self.region_id:
            filtered_query = filtered_query.filter(
                shop__location__region_id=self.region_id
            )

        # Apply country filter if specified
        elif self.country_id:
            filtered_query = filtered_query.filter(
                shop__location__country_id=self.country_id
            )

        # Apply result limit
        return filtered_query[: self.max_results]

    def _apply_location_filters_to_services(self, query):
        """Apply location filters to a service query"""
        # Start with the base query
        filtered_query = query

        # If we have user coordinates, filter by shop distance
        if self.user_location:
            filtered_query = (
                filtered_query.filter(
                    shop__location__location__dwithin=(
                        self.user_location,
                        D(km=self.radius_km),
                    )
                )
                .annotate(
                    distance=Distance("shop__location__location", self.user_location)
                )
                .order_by("distance")
            )

        # If we have city but no coordinates, filter by city
        elif self.city_id:
            filtered_query = filtered_query.filter(shop__location__city_id=self.city_id)

        # Apply region filter if specified
        elif self.region_id:
            filtered_query = filtered_query.filter(
                shop__location__region_id=self.region_id
            )

        # Apply country filter if specified
        elif self.country_id:
            filtered_query = filtered_query.filter(
                shop__location__country_id=self.country_id
            )

        # Apply result limit
        return filtered_query[: self.max_results]

    def _format_shop_results(self, shops):
        """
        Format shop query results with distance information

        Args:
            shops: QuerySet of shops with distance annotation

        Returns:
            List of formatted shop dictionaries
        """
        results = []

        for shop in shops:
            # Get distance if available
            distance_km = None
            if hasattr(shop, "distance"):
                distance_km = shop.distance.km

            # Calculate relevance score if enabled
            relevance_score = 1.0
            if self.apply_relevance_score and distance_km is not None:
                # Score decreases with distance (1.0 at 0km, 0.5 at radius_km)
                relevance_score = max(0.5, 1.0 - (distance_km / (self.radius_km * 2)))

            # Get location information
            location_data = None
            if hasattr(shop, "location") and shop.location:
                location_data = {
                    "latitude": (
                        shop.location.location.y
                        if hasattr(shop.location, "location") and shop.location.location
                        else None
                    ),
                    "longitude": (
                        shop.location.location.x
                        if hasattr(shop.location, "location") and shop.location.location
                        else None
                    ),
                    "address": shop.location.address,
                    "city": shop.location.city.name if shop.location.city else None,
                    "region": (
                        shop.location.region.name if shop.location.region else None
                    ),
                    "country": (
                        shop.location.country.name if shop.location.country else None
                    ),
                }

            # Create result dictionary
            result = {
                "id": shop.id,
                "name": shop.name,
                "rating": shop.rating,
                "location": location_data,
                "distance_km": (
                    round(distance_km, 1) if distance_km is not None else None
                ),
                "relevance_score": round(relevance_score, 2),
            }

            results.append(result)

        # Sort by relevance if enabled
        if self.apply_relevance_score:
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return results

    def _format_reel_results(self, reels):
        """Format reel query results with shop distance information"""
        results = []

        for reel in reels:
            # Get distance if available
            distance_km = None
            if hasattr(reel, "distance"):
                distance_km = reel.distance.km

            # Calculate relevance score if enabled
            relevance_score = 1.0
            if self.apply_relevance_score and distance_km is not None:
                # Score decreases with distance (1.0 at 0km, 0.5 at radius_km)
                relevance_score = max(0.5, 1.0 - (distance_km / (self.radius_km * 2)))

            # Create result dictionary
            result = {
                "id": reel.id,
                "caption": reel.caption,
                "video_url": reel.video_url,
                "thumbnail_url": reel.thumbnail_url,
                "created_at": reel.created_at.isoformat(),
                "shop": {
                    "id": reel.shop_id,
                    "name": reel.shop.name if hasattr(reel, "shop") else None,
                },
                "distance_km": (
                    round(distance_km, 1) if distance_km is not None else None
                ),
                "relevance_score": round(relevance_score, 2),
            }

            results.append(result)

        # Sort by relevance if enabled
        if self.apply_relevance_score:
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return results

    def _format_story_results(self, stories):
        """Format story query results with shop distance information"""
        # Similar to reels
        results = []

        for story in stories:
            # Get distance if available
            distance_km = None
            if hasattr(story, "distance"):
                distance_km = story.distance.km

            # Calculate relevance score if enabled
            relevance_score = 1.0
            if self.apply_relevance_score and distance_km is not None:
                # Score decreases with distance (1.0 at 0km, 0.5 at radius_km)
                relevance_score = max(0.5, 1.0 - (distance_km / (self.radius_km * 2)))

            # Create result dictionary
            result = {
                "id": story.id,
                "media_url": story.media_url,
                "media_type": story.media_type,
                "created_at": story.created_at.isoformat(),
                "shop": {
                    "id": story.shop_id,
                    "name": story.shop.name if hasattr(story, "shop") else None,
                },
                "distance_km": (
                    round(distance_km, 1) if distance_km is not None else None
                ),
                "relevance_score": round(relevance_score, 2),
            }

            results.append(result)

        # Sort by relevance if enabled
        if self.apply_relevance_score:
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return results

    def _format_service_results(self, services):
        """Format service query results with shop distance information"""
        results = []

        for service in services:
            # Get distance if available
            distance_km = None
            if hasattr(service, "distance"):
                distance_km = service.distance.km

            # Calculate relevance score if enabled
            relevance_score = 1.0
            if self.apply_relevance_score and distance_km is not None:
                # Score decreases with distance (1.0 at 0km, 0.5 at radius_km)
                relevance_score = max(0.5, 1.0 - (distance_km / (self.radius_km * 2)))

            # Create result dictionary
            result = {
                "id": service.id,
                "name": service.name,
                "price": float(service.price) if hasattr(service, "price") else None,
                "duration": service.duration,
                "shop": {
                    "id": service.shop_id,
                    "name": service.shop.name if hasattr(service, "shop") else None,
                },
                "distance_km": (
                    round(distance_km, 1) if distance_km is not None else None
                ),
                "relevance_score": round(relevance_score, 2),
            }

            results.append(result)

        # Sort by relevance if enabled
        if self.apply_relevance_score:
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return results

    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculate distance between two points using Haversine formula

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

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

        # Radius of earth in kilometers
        r = 6371

        return c * r


# Convenience function for direct access
location_filter = LocationContentFilter
