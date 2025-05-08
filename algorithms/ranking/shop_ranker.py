import logging
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ShopRanker:
    """
    Advanced algorithm for ranking shops based on multiple factors including
    ratings, location, services offered, and customer preferences.

    This algorithm enhances shop discovery by:
    1. Considering comprehensive ranking factors
    2. Personalizing results based on customer history
    3. Accounting for location relevance
    4. Incorporating business performance metrics
    5. Balancing exploration and exploitation
    """

    def __init__(
        self,
        rating_weight: float = 2.0,
        location_weight: float = 1.5,
        service_match_weight: float = 1.2,
        specialist_quality_weight: float = 1.0,
        review_count_weight: float = 0.8,
        booking_count_weight: float = 0.7,
        content_quality_weight: float = 0.5,
        verified_boost: float = 1.2,
        following_boost: float = 1.3,
        exploration_factor: float = 0.2,
    ):
        """
        Initialize the shop ranker with configurable weights.

        Args:
            rating_weight: Weight for shop rating factor
            location_weight: Weight for proximity/location relevance
            service_match_weight: Weight for service offering match
            specialist_quality_weight: Weight for specialist quality
            review_count_weight: Weight for number of reviews
            booking_count_weight: Weight for booking popularity
            content_quality_weight: Weight for content engagement
            verified_boost: Boost factor for verified shops
            following_boost: Boost factor for shops the user follows
            exploration_factor: Factor for discovery of new shops
        """
        self.rating_weight = rating_weight
        self.location_weight = location_weight
        self.service_match_weight = service_match_weight
        self.specialist_quality_weight = specialist_quality_weight
        self.review_count_weight = review_count_weight
        self.booking_count_weight = booking_count_weight
        self.content_quality_weight = content_quality_weight
        self.verified_boost = verified_boost
        self.following_boost = following_boost
        self.exploration_factor = exploration_factor

    def rank_shops(
        self,
        shops: List[Dict],
        customer_data: Optional[Dict] = None,
        search_params: Optional[Dict] = None,
        location_data: Optional[Dict] = None,
        limit: int = 20,
        offset: int = 0,
        include_factors: bool = False,
    ) -> Dict:
        """
        Rank shops based on multiple factors.

        Args:
            shops: List of shop objects with fields:
                - id: Unique identifier
                - name: Shop name
                - average_rating: Average rating score
                - review_count: Number of reviews
                - booking_count: Number of bookings
                - specialist_count: Number of specialists
                - service_count: Number of services
                - location: Dict with latitude and longitude
                - city: Shop city
                - services: List of service IDs offered
                - categories: List of category IDs covered
                - is_verified: Whether shop is verified
                - content_engagement: Optional content engagement metrics
            customer_data: Optional dict with customer preferences:
                - id: Customer ID
                - previous_bookings: List of previous booking records
                - followed_shops: List of followed shop IDs
                - preferred_categories: List of preferred categories
                - search_history: Previous search terms
                - location: Dict with latitude and longitude
            search_params: Optional search parameters:
                - query: Search query text
                - categories: List of category IDs to filter by
                - services: List of service IDs to filter by
                - rating_min: Minimum rating threshold
            location_data: Optional location data (lat/long) for proximity calculation
            limit: Maximum number of shops to return
            offset: Number of shops to skip (for pagination)
            include_factors: Whether to include ranking factors in response

        Returns:
            A dictionary containing:
            - ranked_shops: List of shops sorted by relevance
            - total_count: Total number of matching shops
            - ranking_factors: Explanation of how shops were ranked (if requested)
        """
        # Initialize result
        result = {"ranked_shops": [], "total_count": 0}

        if not shops:
            return result

        # Apply initial filtering based on search parameters
        filtered_shops = self._apply_filters(shops, search_params)

        # Calculate scores for all filtered shops
        scored_shops = []
        all_factors = {}

        for shop in filtered_shops:
            # Create a copy of shop to avoid modifying original
            shop_copy = shop.copy()
            shop_id = shop["id"]

            # Calculate ranking factors
            factors = self._calculate_ranking_factors(
                shop, customer_data, location_data
            )

            # Apply weights to each factor
            weighted_score = (
                factors["rating"] * self.rating_weight
                + factors["location"] * self.location_weight
                + factors["service_match"] * self.service_match_weight
                + factors["specialist_quality"] * self.specialist_quality_weight
                + factors["review_count"] * self.review_count_weight
                + factors["booking_count"] * self.booking_count_weight
                + factors["content_quality"] * self.content_quality_weight
            )

            # Apply boosts
            if factors["is_verified"]:
                weighted_score *= self.verified_boost

            if factors["is_followed"]:
                weighted_score *= self.following_boost

            # Apply exploration factor for discovery
            if self.exploration_factor > 0:
                import random

                exploration_boost = 1.0 + (random.random() * self.exploration_factor)
                weighted_score *= exploration_boost
                factors["exploration"] = exploration_boost

            # Store score in shop copy
            shop_copy["_score"] = weighted_score

            # Store factors if requested
            if include_factors:
                all_factors[shop_id] = factors

            scored_shops.append(shop_copy)

        # Sort shops by score (highest first)
        ranked_shops = sorted(
            scored_shops, key=lambda x: x.get("_score", 0), reverse=True
        )

        # Apply pagination
        paginated_shops = (
            ranked_shops[offset : offset + limit] if limit > 0 else ranked_shops
        )

        # Cleanup - remove internal score
        for shop in paginated_shops:
            if "_score" in shop:
                shop.pop("_score")

        # Set result fields
        result["ranked_shops"] = paginated_shops
        result["total_count"] = len(filtered_shops)

        if include_factors:
            result["ranking_factors"] = all_factors

        return result

    def _apply_filters(
        self, shops: List[Dict], search_params: Optional[Dict]
    ) -> List[Dict]:
        """
        Apply initial filtering based on search parameters.
        """
        # If no search params, return all shops
        if not search_params:
            return shops

        filtered_shops = shops

        # Filter by category if specified
        if "categories" in search_params and search_params["categories"]:
            categories = set(search_params["categories"])
            filtered_shops = [
                shop
                for shop in filtered_shops
                if set(shop.get("categories", [])).intersection(categories)
            ]

        # Filter by service if specified
        if "services" in search_params and search_params["services"]:
            services = set(search_params["services"])
            filtered_shops = [
                shop
                for shop in filtered_shops
                if set(shop.get("services", [])).intersection(services)
            ]

        # Filter by minimum rating if specified
        if "rating_min" in search_params and search_params["rating_min"]:
            min_rating = float(search_params["rating_min"])
            filtered_shops = [
                shop
                for shop in filtered_shops
                if shop.get("average_rating", 0) >= min_rating
            ]

        # Filter by text query if specified
        if "query" in search_params and search_params["query"]:
            query = search_params["query"].lower()
            filtered_shops = [
                shop
                for shop in filtered_shops
                if (
                    query in shop.get("name", "").lower()
                    or query in shop.get("description", "").lower()
                )
            ]

        return filtered_shops

    def _calculate_ranking_factors(
        self, shop: Dict, customer_data: Optional[Dict], location_data: Optional[Dict]
    ) -> Dict:
        """
        Calculate all ranking factors for a shop.
        """
        factors = {
            "rating": 0.0,
            "location": 0.0,
            "service_match": 0.0,
            "specialist_quality": 0.0,
            "review_count": 0.0,
            "booking_count": 0.0,
            "content_quality": 0.0,
            "is_verified": shop.get("is_verified", False),
            "is_followed": False,
        }

        # Calculate rating score (0.0-1.0)
        avg_rating = shop.get("average_rating", 0)
        if avg_rating > 0:
            # Normalize rating to 0-1 scale (assuming 1-5 rating scale)
            factors["rating"] = (avg_rating - 1) / 4.0

        # Calculate location score if location data provided
        if location_data:
            factors["location"] = self._calculate_location_score(shop, location_data)

        # Calculate service match score if customer data provided
        if customer_data:
            factors["service_match"] = self._calculate_service_match(
                shop, customer_data
            )

            # Check if shop is followed
            followed_shops = customer_data.get("followed_shops", [])
            factors["is_followed"] = shop["id"] in followed_shops

        # Calculate specialist quality score
        factors["specialist_quality"] = self._calculate_specialist_quality(shop)

        # Calculate review count score
        review_count = shop.get("review_count", 0)
        # Normalize using logarithmic scale (diminishing returns for high counts)
        factors["review_count"] = min(1.0, math.log10(max(1, review_count)) / 3.0)

        # Calculate booking count score
        booking_count = shop.get("booking_count", 0)
        # Normalize using logarithmic scale
        factors["booking_count"] = min(1.0, math.log10(max(1, booking_count)) / 4.0)

        # Calculate content quality score
        factors["content_quality"] = self._calculate_content_quality(shop)

        return factors

    def _calculate_location_score(self, shop: Dict, location_data: Dict) -> float:
        """
        Calculate location score based on distance.
        """
        # Get user location
        user_lat = location_data.get("latitude")
        user_lng = location_data.get("longitude")

        # Get shop location
        shop_location = shop.get("location", {})
        shop_lat = shop_location.get("latitude")
        shop_lng = shop_location.get("longitude")

        # If location data is missing, return neutral score
        if not user_lat or not user_lng or not shop_lat or not shop_lng:
            return 0.5

        # Calculate distance in kilometers
        distance_km = self._calculate_distance(user_lat, user_lng, shop_lat, shop_lng)

        # Convert distance to score (closer is better)
        # Using an exponential decay function: score = exp(-distance/scale)
        # Distance of 0km = score 1.0
        # Distance of 5km = score ~0.37
        # Distance of 10km = score ~0.14
        location_score = math.exp(-distance_km / 5.0)

        return location_score

    def _calculate_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.
        """
        from math import atan2, cos, radians, sin, sqrt

        # Convert latitude and longitude from degrees to radians
        lat1_rad = radians(float(lat1))
        lng1_rad = radians(float(lng1))
        lat2_rad = radians(float(lat2))
        lng2_rad = radians(float(lng2))

        # Haversine formula
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Earth radius in kilometers
        radius = 6371.0

        # Calculate distance
        distance = radius * c

        return distance

    def _calculate_service_match(self, shop: Dict, customer_data: Dict) -> float:
        """
        Calculate service match score based on customer preferences.
        """
        # Get customer preferred categories
        preferred_categories = set(customer_data.get("preferred_categories", []))

        # Get shop categories
        shop_categories = set(shop.get("categories", []))

        # If no preferences or shop has no categories, return neutral score
        if not preferred_categories or not shop_categories:
            return 0.5

        # Calculate category overlap
        overlap = preferred_categories.intersection(shop_categories)

        # Calculate match ratio based on customer preferences (how many of the
        # customer's preferences does this shop satisfy)
        if preferred_categories:
            match_ratio = len(overlap) / len(preferred_categories)
        else:
            match_ratio = 0.0

        # Adjust score to prevent zero score
        service_match_score = 0.2 + (0.8 * match_ratio)

        # Also consider past bookings as an indication of preference
        previous_bookings = customer_data.get("previous_bookings", [])
        shop_bookings = [b for b in previous_bookings if b.get("shop_id") == shop["id"]]

        if shop_bookings:
            # Boost score based on number of previous bookings (cap at 5 bookings)
            booking_boost = min(1.5, 1.0 + (len(shop_bookings) * 0.1))
            service_match_score *= booking_boost

        return min(1.0, service_match_score)  # Cap at 1.0

    def _calculate_specialist_quality(self, shop: Dict) -> float:
        """
        Calculate specialist quality score.
        """
        # Get specialist data
        specialist_count = shop.get("specialist_count", 0)
        specialist_avg_rating = shop.get("specialist_avg_rating")

        # If no specialists or rating, return neutral score
        if specialist_count == 0 or specialist_avg_rating is None:
            return 0.5

        # Normalize specialist rating to 0-1 scale
        if isinstance(specialist_avg_rating, (int, float)):
            normalized_rating = (specialist_avg_rating - 1) / 4.0
        else:
            normalized_rating = 0.5

        # Factor in specialist count (diminishing returns)
        # More specialists is generally better, up to a point
        count_factor = min(1.0, math.log10(specialist_count + 1) / math.log10(11))

        # Combine factors (weighted more toward rating quality)
        specialist_score = (normalized_rating * 0.7) + (count_factor * 0.3)

        return specialist_score

    def _calculate_content_quality(self, shop: Dict) -> float:
        """
        Calculate content quality score based on engagement metrics.
        """
        # Get content engagement metrics
        content_engagement = shop.get("content_engagement", {})

        # If no engagement data, return neutral score
        if not content_engagement:
            return 0.5

        # Calculate quality based on average engagement metrics
        total_engagement = 0
        engagement_count = 0

        # Consider various types of engagement
        for content_type, metrics in content_engagement.items():
            if content_type in ["reels", "stories"]:
                # Get engagement values
                likes = metrics.get("likes", 0)
                comments = metrics.get("comments", 0)
                views = metrics.get("views", 0)
                shares = metrics.get("shares", 0)

                # Skip if no views (content not viewed)
                if views == 0:
                    continue

                # Calculate engagement rate
                # Weight different engagement types differently
                engagement_rate = (
                    (likes * 1.0) + (comments * 3.0) + (shares * 5.0)
                ) / views

                # Cap the rate at a reasonable maximum
                capped_rate = min(engagement_rate, 0.5)

                # Normalize to 0-1 scale
                normalized_rate = capped_rate / 0.5

                total_engagement += normalized_rate
                engagement_count += 1

        # Calculate average engagement across all content types
        if engagement_count > 0:
            avg_engagement = total_engagement / engagement_count
        else:
            avg_engagement = 0.5  # Neutral score

        return avg_engagement
