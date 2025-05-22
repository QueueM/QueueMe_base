"""
Content recommendation engine for Queue Me platform.

This module contains sophisticated algorithms for recommending content to users
based on their preferences, behavior, and location.

It supports three main recommendation types:
1. "For You" feed - Personalized content recommendations
2. Specialist recommendations - Finding the best specialists based on user preferences
3. Shop recommendations - Finding relevant shops based on location and preferences
"""

import logging
from datetime import timedelta
from typing import Dict, List, Tuple

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class ContentRecommender:
    """Content recommendation engine for personalized content feeds."""

    # Weights for different ranking factors
    CATEGORY_MATCH_WEIGHT = 3.0
    ENGAGEMENT_WEIGHT = 2.5
    RECENCY_WEIGHT = 2.0
    LOCATION_WEIGHT = 3.0
    POPULARITY_WEIGHT = 1.5
    FOLLOWING_BONUS = 5.0
    VERIFIED_BONUS = 1.0

    def __init__(self, customer_id: str = None):
        """
        Initialize the recommender.

        Args:
            customer_id: The ID of the customer to generate recommendations for
        """
        self.customer_id = customer_id

    def generate_for_you_feed(self, city: str = None, limit: int = 20) -> List[Dict]:
        """
        Generate a personalized "For You" feed based on user preferences and behavior.

        Args:
            city: City to filter content by (same-city requirement)
            limit: Maximum number of items to return

        Returns:
            List of recommended content items sorted by relevance
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.services.preference_extractor import (
                CustomerPreferenceExtractor,
            )
            from apps.reelsapp.models import Reel

            # Get customer preferences
            preferences = {}
            if self.customer_id:
                extractor = CustomerPreferenceExtractor(self.customer_id)
                preferences = extractor.extract_preferences()

            # Basic query with city filter
            query = Q(shop__location__city=city) if city else Q()

            # Add is_active filter
            query &= Q(is_active=True)

            # Get base queryset
            reels = Reel.objects.filter(query)

            # Score and rank the content
            scored_content = self._score_content(reels, preferences)

            # Sort by score descending and limit results
            recommendations = sorted(
                scored_content, key=lambda x: x["score"], reverse=True
            )[:limit]

            return [item["content"] for item in recommendations]

        except Exception as e:
            logger.exception(f"Error generating For You feed: {str(e)}")
            return []

    def _score_content(self, content_queryset, preferences: Dict) -> List[Dict]:
        """
        Score content based on user preferences and content attributes.

        Args:
            content_queryset: QuerySet of content items
            preferences: Dictionary of user preferences

        Returns:
            List of dictionaries with content and score
        """
        scored_content = []

        # Get followed shops if customer_id is provided
        followed_shop_ids = []
        if self.customer_id:
            from apps.followapp.models import Follow

            followed_shop_ids = Follow.objects.filter(
                customer_id=self.customer_id, content_type__model="shop"
            ).values_list("object_id", flat=True)

        # Score each content item
        for item in content_queryset:
            score = 0.0

            # Category match score
            if preferences.get("categories") and hasattr(item, "category"):
                category_id = getattr(item, "category_id", None)
                if category_id and category_id in preferences["categories"]:
                    category_weight = preferences["categories"].get(category_id, 0)
                    score += category_weight * self.CATEGORY_MATCH_WEIGHT

            # Engagement score based on likes, comments, etc.
            engagement_score = self._calculate_engagement_score(item)
            score += engagement_score * self.ENGAGEMENT_WEIGHT

            # Recency score - newer content ranks higher
            recency_score = self._calculate_recency_score(item.created_at)
            score += recency_score * self.RECENCY_WEIGHT

            # Location relevance (distance from customer if available)
            if (
                hasattr(item, "shop")
                and hasattr(item.shop, "location")
                and preferences.get("location")
            ):
                from algorithms.geo.distance import haversine_distance

                customer_location = preferences.get("location")
                shop_location = (
                    item.shop.location.latitude,
                    item.shop.location.longitude,
                )

                # Convert distance to a score (closer is better)
                distance = haversine_distance(customer_location, shop_location)
                # Max distance considered is 50km, normalize to 0-1 range and invert
                # (closer is better)
                distance_score = max(0, 1 - (distance / 50))
                score += distance_score * self.LOCATION_WEIGHT

            # Following bonus - content from shops the customer follows
            if hasattr(item, "shop") and item.shop.id in followed_shop_ids:
                score += self.FOLLOWING_BONUS

            # Verified status bonus
            if hasattr(item, "shop") and item.shop.is_verified:
                score += self.VERIFIED_BONUS

            # Add to scored content list
            scored_content.append({"content": item, "score": score})

        return scored_content

    def _calculate_engagement_score(self, content_item) -> float:
        """
        Calculate engagement score based on likes, comments, shares, etc.

        Args:
            content_item: The content item to score

        Returns:
            Normalized engagement score (0-1)
        """
        # Base score
        score = 0.0

        # Different types of content have different engagement metrics
        if hasattr(content_item, "likes_count"):
            score += min(content_item.likes_count * 0.1, 5.0)  # Cap at 5.0

        if hasattr(content_item, "comments_count"):
            score += min(
                content_item.comments_count * 0.2, 5.0
            )  # Comments worth more than likes

        if hasattr(content_item, "shares_count"):
            score += min(
                content_item.shares_count * 0.3, 5.0
            )  # Shares worth more than comments

        if hasattr(content_item, "views_count"):
            # Views have less weight but still matter
            score += min(content_item.views_count * 0.01, 5.0)

        # Normalize to 0-1 range
        return min(score / 15.0, 1.0)

    def _calculate_recency_score(self, created_at) -> float:
        """
        Calculate recency score based on content creation date.

        Args:
            created_at: Creation timestamp

        Returns:
            Recency score (0-1), with newer content scoring higher
        """
        if not created_at:
            return 0

        now = timezone.now()
        age_in_days = (now - created_at).total_seconds() / 86400  # Convert to days

        # Content less than a day old gets max score
        if age_in_days < 1:
            return 1.0

        # Content 1-7 days old gets linearly decreasing score
        elif age_in_days < 7:
            return 1.0 - ((age_in_days - 1) / 6)

        # Content 7-30 days old gets lower score
        elif age_in_days < 30:
            return 0.3 - ((age_in_days - 7) / 23 * 0.2)  # From 0.3 down to 0.1

        # Content older than 30 days gets minimal score
        else:
            return max(
                0.1 - ((age_in_days - 30) / 60 * 0.1), 0
            )  # Gradually decrease to 0


class SpecialistRecommender:
    """Specialist recommendation engine for connecting customers with relevant specialists."""

    # Weights for different ranking factors
    RATING_WEIGHT = 3.0
    CATEGORY_MATCH_WEIGHT = 2.5
    BOOKING_COUNT_WEIGHT = 1.0
    VERIFIED_BONUS = 1.5
    PREVIOUS_BOOKING_BONUS = 2.0
    AVAILABILITY_BONUS = 1.5

    def __init__(self, customer_id: str = None):
        """
        Initialize the specialist recommender.

        Args:
            customer_id: The ID of the customer to generate recommendations for
        """
        self.customer_id = customer_id

    def recommend_specialists(
        self,
        city: str = None,
        service_id: str = None,
        category_id: str = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Recommend specialists based on customer preferences and service needs.

        Args:
            city: City to filter specialists by (same-city requirement)
            service_id: Optional service ID to filter specialists by
            category_id: Optional category ID to filter specialists by
            limit: Maximum number of specialists to return

        Returns:
            List of recommended specialists sorted by relevance
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.services.preference_extractor import (
                CustomerPreferenceExtractor,
            )
            from apps.specialistsapp.models import Specialist

            # Get customer preferences
            preferences = {}
            if self.customer_id:
                extractor = CustomerPreferenceExtractor(self.customer_id)
                preferences = extractor.extract_preferences()

            # Build base query
            query = Q()

            # Apply city filter (required for visibility)
            if city:
                query &= Q(employee__shop__location__city=city)

            # Apply service filter if provided
            if service_id:
                query &= Q(specialist_services__service_id=service_id)

            # Apply category filter if provided
            if category_id:
                query &= Q(specialist_services__service__category_id=category_id)

            # Get base queryset
            specialists = Specialist.objects.filter(query).distinct()

            # Score and rank the specialists
            scored_specialists = self._score_specialists(
                specialists, preferences, service_id
            )

            # Sort by score descending and limit results
            recommendations = sorted(
                scored_specialists, key=lambda x: x["score"], reverse=True
            )[:limit]

            return [item["specialist"] for item in recommendations]

        except Exception as e:
            logger.exception(f"Error recommending specialists: {str(e)}")
            return []

    def _score_specialists(
        self, specialist_queryset, preferences: Dict, service_id: str = None
    ) -> List[Dict]:
        """
        Score specialists based on multiple factors.

        Args:
            specialist_queryset: QuerySet of specialists
            preferences: Dictionary of user preferences
            service_id: Optional service ID for specialized scoring

        Returns:
            List of dictionaries with specialist and score
        """
        scored_specialists = []

        # Get customer's previous bookings with specialists if available
        previous_specialist_ids = []
        if self.customer_id:
            from apps.bookingapp.models import Appointment

            previous_specialist_ids = (
                Appointment.objects.filter(
                    customer_id=self.customer_id,
                    status__in=["completed", "cancelled", "no_show"],
                )
                .values_list("specialist_id", flat=True)
                .distinct()
            )

        # Score each specialist
        for specialist in specialist_queryset:
            score = 0.0

            # Rating score (if available)
            if hasattr(specialist, "average_rating") and specialist.average_rating:
                # Scale from 1-5 to 0-1
                rating_score = (specialist.average_rating - 1) / 4
                score += rating_score * self.RATING_WEIGHT

            # Category match score
            if preferences.get("categories"):
                # Get specialist's service categories
                from apps.serviceapp.models import Service

                service_categories = (
                    Service.objects.filter(specialist_services__specialist=specialist)
                    .values_list("category_id", flat=True)
                    .distinct()
                )

                # Calculate match score based on preference strength
                category_score = 0
                for category_id in service_categories:
                    if category_id in preferences["categories"]:
                        category_score += preferences["categories"].get(category_id, 0)

                # Normalize (0-1) and add to score
                if service_categories:
                    category_score = min(category_score / len(service_categories), 1.0)
                    score += category_score * self.CATEGORY_MATCH_WEIGHT

            # Booking count / popularity
            booking_count = getattr(specialist, "booking_count", 0)
            if booking_count:
                # Normalize booking count (cap at 100 for scoring)
                booking_score = min(booking_count / 100, 1.0)
                score += booking_score * self.BOOKING_COUNT_WEIGHT

            # Verification status bonus
            if specialist.is_verified:
                score += self.VERIFIED_BONUS

            # Previous booking with this specialist bonus
            if specialist.id in previous_specialist_ids:
                score += self.PREVIOUS_BOOKING_BONUS

            # Availability bonus (if service_id provided, check availability)
            if service_id:
                available = self._check_specialist_availability(
                    specialist.id, service_id
                )
                if available:
                    score += self.AVAILABILITY_BONUS

            # Add to scored specialists list
            scored_specialists.append({"specialist": specialist, "score": score})

        return scored_specialists

    def _check_specialist_availability(
        self, specialist_id: str, service_id: str
    ) -> bool:
        """
        Check if specialist is available for a service in the near future.

        Args:
            specialist_id: The specialist ID
            service_id: The service ID

        Returns:
            Boolean indicating if specialist has availability
        """
        try:
            # This is a simplified version, the full implementation would query
            # the booking system for actual availability slots
            from apps.serviceapp.services.availability_service import (
                AvailabilityService,
            )

            # Check for any availability in the next 7 days
            today = timezone.now().date()
            for i in range(7):
                check_date = today + timedelta(days=i)
                slots = AvailabilityService.get_specialist_availability(
                    specialist_id, service_id, check_date
                )
                if slots:
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error checking specialist availability: {str(e)}")
            # Default to True if we can't check availability to avoid penalizing specialists
            return True


class ShopRecommender:
    """Shop recommendation engine for discovering relevant businesses."""

    # Weights for different ranking factors
    DISTANCE_WEIGHT = 4.0
    RATING_WEIGHT = 3.0
    POPULARITY_WEIGHT = 2.0
    SERVICE_MATCH_WEIGHT = 2.5
    VERIFIED_BONUS = 1.5
    PREVIOUS_VISIT_BONUS = 2.0
    SUBSCRIPTION_TIER_WEIGHT = 1.0

    def __init__(self, customer_id: str = None):
        """
        Initialize the shop recommender.

        Args:
            customer_id: The ID of the customer to generate recommendations for
        """
        self.customer_id = customer_id

    def recommend_shops(
        self,
        location: Tuple[float, float] = None,
        city: str = None,
        category_id: str = None,
        radius: float = 10.0,  # km
        limit: int = 20,
    ) -> List[Dict]:
        """
        Recommend shops based on location, category, and customer preferences.

        Args:
            location: (latitude, longitude) tuple for proximity calculation
            city: City to filter shops by (same-city requirement)
            category_id: Optional category ID to filter shops by
            radius: Maximum distance in kilometers
            limit: Maximum number of shops to return

        Returns:
            List of recommended shops sorted by relevance
        """
        try:
            # Import here to avoid circular imports
            from algorithms.geo.distance import haversine_distance
            from apps.customersapp.services.preference_extractor import (
                CustomerPreferenceExtractor,
            )
            from apps.shopapp.models import Shop

            # Get customer preferences
            preferences = {}
            if self.customer_id:
                extractor = CustomerPreferenceExtractor(self.customer_id)
                preferences = extractor.extract_preferences()

                # If customer has location in preferences but none provided, use that
                if not location and preferences.get("location"):
                    location = preferences.get("location")

            # Build base query
            query = Q(is_active=True)

            # Apply city filter (required for visibility)
            if city:
                query &= Q(location__city=city)

            # Apply category filter if provided
            if category_id:
                query &= Q(services__category_id=category_id)

            # Get base queryset
            shops = Shop.objects.filter(query).distinct()

            # If location provided, filter by radius first to reduce scoring set
            if location and radius:
                shops_with_distance = []
                for shop in shops:
                    if hasattr(shop, "location") and shop.location:
                        shop_location = (
                            shop.location.latitude,
                            shop.location.longitude,
                        )
                        distance = haversine_distance(location, shop_location)
                        if distance <= radius:
                            shops_with_distance.append((shop, distance))

                # Score shops with distance info
                scored_shops = self._score_shops_with_distance(
                    shops_with_distance, preferences, category_id
                )
            else:
                # Score shops without distance info
                scored_shops = self._score_shops(shops, preferences, category_id)

            # Sort by score descending and limit results
            recommendations = sorted(
                scored_shops, key=lambda x: x["score"], reverse=True
            )[:limit]

            return [item["shop"] for item in recommendations]

        except Exception as e:
            logger.exception(f"Error recommending shops: {str(e)}")
            return []

    def _score_shops_with_distance(
        self,
        shops_with_distance: List[Tuple],
        preferences: Dict,
        category_id: str = None,
    ) -> List[Dict]:
        """
        Score shops with pre-calculated distances.

        Args:
            shops_with_distance: List of (shop, distance) tuples
            preferences: Dictionary of user preferences
            category_id: Optional category ID for relevance calculation

        Returns:
            List of dictionaries with shop and score
        """
        scored_shops = []

        # Get previous visited shops if customer ID available
        previous_shop_ids = []
        if self.customer_id:
            from apps.bookingapp.models import Appointment

            previous_shop_ids = (
                Appointment.objects.filter(customer_id=self.customer_id)
                .values_list("shop_id", flat=True)
                .distinct()
            )

        # Score each shop
        for shop, distance in shops_with_distance:
            score = 0.0

            # Distance score (closer is better)
            # Convert distance to a score (0-1 range), max distance is radius
            distance_score = max(0, 1 - (distance / 10))  # 10km as normalization factor
            score += distance_score * self.DISTANCE_WEIGHT

            # Add other scoring factors
            score += self._calculate_common_shop_score(
                shop, preferences, category_id, previous_shop_ids
            )

            # Add to scored shops list
            scored_shops.append({"shop": shop, "score": score, "distance": distance})

        return scored_shops

    def _score_shops(
        self, shop_queryset, preferences: Dict, category_id: str = None
    ) -> List[Dict]:
        """
        Score shops without distance information.

        Args:
            shop_queryset: QuerySet of shops
            preferences: Dictionary of user preferences
            category_id: Optional category ID for relevance calculation

        Returns:
            List of dictionaries with shop and score
        """
        scored_shops = []

        # Get previous visited shops if customer ID available
        previous_shop_ids = []
        if self.customer_id:
            from apps.bookingapp.models import Appointment

            previous_shop_ids = (
                Appointment.objects.filter(customer_id=self.customer_id)
                .values_list("shop_id", flat=True)
                .distinct()
            )

        # Score each shop
        for shop in shop_queryset:
            score = self._calculate_common_shop_score(
                shop, preferences, category_id, previous_shop_ids
            )

            # Add to scored shops list
            scored_shops.append({"shop": shop, "score": score})

        return scored_shops

    def _calculate_common_shop_score(
        self,
        shop,
        preferences: Dict,
        category_id: str = None,
        previous_shop_ids: List[str] = None,
    ) -> float:
        """
        Calculate common shop scoring factors.

        Args:
            shop: Shop object to score
            preferences: Dictionary of user preferences
            category_id: Optional category ID for relevance calculation
            previous_shop_ids: List of previously visited shop IDs

        Returns:
            Shop score based on common factors
        """
        score = 0.0

        # Rating score (if available)
        if hasattr(shop, "average_rating") and shop.average_rating:
            # Scale from 1-5 to 0-1
            rating_score = (shop.average_rating - 1) / 4
            score += rating_score * self.RATING_WEIGHT

        # Service/category match score
        if preferences.get("categories") or category_id:
            # Get shop's service categories
            from apps.serviceapp.models import Service

            service_categories = (
                Service.objects.filter(shop=shop)
                .values_list("category_id", flat=True)
                .distinct()
            )

            category_score = 0
            # If specific category requested, check if shop offers it
            if category_id and category_id in service_categories:
                category_score = 1.0
            # Otherwise check against preferences
            elif preferences.get("categories"):
                for category_id in service_categories:
                    if category_id in preferences["categories"]:
                        category_score += preferences["categories"].get(category_id, 0)

                # Normalize (0-1)
                if service_categories:
                    category_score = min(category_score / len(service_categories), 1.0)

            score += category_score * self.SERVICE_MATCH_WEIGHT

        # Popularity - based on booking count
        booking_count = getattr(shop, "booking_count", 0)
        if booking_count:
            # Normalize booking count (cap at 500 for scoring)
            popularity_score = min(booking_count / 500, 1.0)
            score += popularity_score * self.POPULARITY_WEIGHT

        # Verification status bonus
        if shop.is_verified:
            score += self.VERIFIED_BONUS

        # Previous visit bonus
        if previous_shop_ids and shop.id in previous_shop_ids:
            score += self.PREVIOUS_VISIT_BONUS

        # Subscription tier bonus (premium shops get more visibility)
        if hasattr(shop, "company") and hasattr(shop.company, "subscription"):
            subscription = shop.company.subscription
            if subscription and subscription.plan:
                tier_score = 0
                if subscription.plan.name == "Premium":
                    tier_score = 1.0
                elif subscription.plan.name == "Business":
                    tier_score = 0.7
                elif subscription.plan.name == "Basic":
                    tier_score = 0.4

                score += tier_score * self.SUBSCRIPTION_TIER_WEIGHT

        return score
