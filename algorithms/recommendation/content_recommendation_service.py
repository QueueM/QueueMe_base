"""
Content Recommendation Service

This module provides advanced recommendation algorithms for content (reels, stories, services)
based on user behavior, content similarity, and real-time popularity metrics.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
from django.core.cache import cache
from django.db import connection
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q

from apps.categoriesapp.models import Category
from apps.customersapp.models import Customer
from apps.followapp.models import Follow
from apps.geoapp.models import Location
from apps.reelsapp.models import Reel, ReelComment, ReelLike, ReelView
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story, StoryView

logger = logging.getLogger(__name__)


class ContentRecommendationService:
    """
    Service for generating personalized content recommendations
    using advanced machine learning techniques.
    """

    # Constants for algorithm tuning
    RECENCY_WEIGHT = 0.3
    POPULARITY_WEIGHT = 0.25
    RELEVANCE_WEIGHT = 0.2
    ENGAGEMENT_WEIGHT = 0.15
    LOCATION_WEIGHT = 0.1

    # Cache TTLs
    POPULARITY_CACHE_TTL = 60 * 15  # 15 minutes
    RECOMMENDATION_CACHE_TTL = 60 * 10  # 10 minutes

    def __init__(self):
        self.similarity_matrix = None
        self.category_vectors = {}
        self.content_embeddings = {}

    def get_personalized_feed(self, customer, feed_type="for_you", limit=20, offset=0):
        """
        Generate a personalized content feed for a customer

        Args:
            customer: The customer to generate recommendations for
            feed_type: Type of feed - 'for_you', 'nearby', or 'following'
            limit: Maximum number of items to return
            offset: Pagination offset

        Returns:
            List of recommended content items with scores
        """
        cache_key = f"content_feed:{customer.id}:{feed_type}:{limit}:{offset}"
        cached_feed = cache.get(cache_key)

        if cached_feed:
            return cached_feed

        if feed_type == "for_you":
            recommendations = self._generate_for_you_feed(customer, limit, offset)
        elif feed_type == "nearby":
            recommendations = self._generate_nearby_feed(customer, limit, offset)
        elif feed_type == "following":
            recommendations = self._generate_following_feed(customer, limit, offset)
        else:
            raise ValueError(f"Unknown feed type: {feed_type}")

        # Cache the results
        cache.set(cache_key, recommendations, self.RECOMMENDATION_CACHE_TTL)

        return recommendations

    def _generate_for_you_feed(self, customer, limit, offset):
        """
        Generate the personalized "For You" feed using collaborative filtering
        and content-based approaches combined into a hybrid model.
        """
        # Get base content pool (from user's city)
        try:
            city = customer.location.city
            base_content = Reel.objects.filter(
                shop__location__city=city,
                is_active=True,
                created_at__gte=datetime.now() - timedelta(days=30),
            ).select_related("shop", "service")
        except Exception as e:
            logger.error(f"Error getting base content: {e}")
            base_content = Reel.objects.filter(
                is_active=True, created_at__gte=datetime.now() - timedelta(days=30)
            ).select_related("shop", "service")

        # Get user interaction history
        viewed_reels = set(
            ReelView.objects.filter(customer=customer).values_list("reel_id", flat=True)
        )

        liked_reels = set(
            ReelLike.objects.filter(customer=customer).values_list("reel_id", flat=True)
        )

        commented_reels = set(
            ReelComment.objects.filter(customer=customer).values_list("reel_id", flat=True)
        )

        # Get user preferences
        preferred_categories = self._get_user_preferred_categories(customer)
        preferred_shops = self._get_user_preferred_shops(customer)

        # Calculate content scores
        scored_content = []
        for reel in base_content:
            # Don't recommend already viewed content too often
            if (
                reel.id in viewed_reels and np.random.random() > 0.2
            ):  # 20% chance to include viewed content
                continue

            # Calculate content score components
            recency_score = self._calculate_recency_score(reel.created_at)
            popularity_score = self._get_content_popularity_score(reel)
            relevance_score = self._calculate_relevance_score(reel, preferred_categories)
            engagement_score = self._calculate_engagement_score(reel, liked_reels, commented_reels)

            # Merge scores with weights
            total_score = (
                recency_score * self.RECENCY_WEIGHT
                + popularity_score * self.POPULARITY_WEIGHT
                + relevance_score * self.RELEVANCE_WEIGHT
                + engagement_score * self.ENGAGEMENT_WEIGHT
            )

            # Add shop preference boost
            if reel.shop_id in preferred_shops:
                total_score *= 1.2

            scored_content.append(
                {
                    "content": reel,
                    "score": total_score,
                    "components": {
                        "recency": recency_score,
                        "popularity": popularity_score,
                        "relevance": relevance_score,
                        "engagement": engagement_score,
                    },
                }
            )

        # Sort by score and apply pagination
        scored_content.sort(key=lambda x: x["score"], reverse=True)
        paginated_content = scored_content[offset : offset + limit]

        # Log recommendation details for analysis
        self._log_recommendations(customer, paginated_content, feed_type="for_you")

        return paginated_content

    def _generate_nearby_feed(self, customer, limit, offset):
        """
        Generate the "Nearby" feed based on geographic proximity
        but also incorporating some personalization
        """
        try:
            # Get customer location
            customer_location = customer.location
            if not customer_location:
                raise ValueError("Customer location not available")

            # Get reels from shops in same city, ordered by distance
            nearby_content = self._get_nearby_content(
                customer_location, limit * 2
            )  # Get more and filter

            # Score by distance and some personalization
            scored_content = []
            for content_item in nearby_content:
                distance = content_item["distance"]

                # Convert distance to a 0-1 score (closer is higher)
                # Using an exponential decay function
                distance_score = np.exp(-0.2 * distance)  # Decay parameter can be tuned

                # Get some personalization factors
                recency_score = self._calculate_recency_score(content_item["content"].created_at)
                popularity_score = self._get_content_popularity_score(content_item["content"])

                # Calculate total score (mostly distance, with some personalization)
                total_score = distance_score * 0.7 + recency_score * 0.2 + popularity_score * 0.1

                scored_content.append(
                    {
                        "content": content_item["content"],
                        "score": total_score,
                        "distance": distance,
                        "components": {
                            "distance": distance_score,
                            "recency": recency_score,
                            "popularity": popularity_score,
                        },
                    }
                )

            # Sort and paginate
            scored_content.sort(key=lambda x: x["score"], reverse=True)
            paginated_content = scored_content[offset : offset + limit]

            return paginated_content

        except Exception as e:
            logger.error(f"Error generating nearby feed: {e}")
            # Fallback to basic recency-based feed
            return self._generate_fallback_feed(limit, offset)

    def _generate_following_feed(self, customer, limit, offset):
        """
        Generate a feed based on shops the customer follows
        """
        # Get shops the customer follows
        followed_shop_ids = Follow.objects.filter(customer=customer).values_list(
            "shop_id", flat=True
        )

        # Get content from followed shops
        followed_content = (
            Reel.objects.filter(shop_id__in=followed_shop_ids, is_active=True)
            .select_related("shop", "service")
            .order_by("-created_at")
        )

        # Score content (primarily by recency)
        scored_content = []
        for reel in followed_content:
            recency_score = self._calculate_recency_score(reel.created_at)
            popularity_score = self._get_content_popularity_score(reel)

            # Calculate total score (recency-focused)
            total_score = recency_score * 0.7 + popularity_score * 0.3

            scored_content.append(
                {
                    "content": reel,
                    "score": total_score,
                    "components": {
                        "recency": recency_score,
                        "popularity": popularity_score,
                    },
                }
            )

        # Sort and paginate
        scored_content.sort(key=lambda x: x["score"], reverse=True)
        paginated_content = scored_content[offset : offset + limit]

        return paginated_content

    def _calculate_recency_score(self, created_at):
        """
        Calculate a recency score (0-1) based on content age
        Newer content gets higher score
        """
        # Calculate age in days
        age_days = (datetime.now() - created_at).total_seconds() / (24 * 3600)

        # Apply exponential decay
        # Content 30 days old gets a score of ~0.05
        return np.exp(-0.1 * age_days)

    def _get_content_popularity_score(self, content):
        """
        Get the popularity score for content based on engagement metrics
        """
        cache_key = f"content_popularity:{content.id}"
        cached_score = cache.get(cache_key)

        if cached_score is not None:
            return cached_score

        try:
            # Get metrics
            views = content.views.count()
            likes = content.likes.count()
            comments = content.comments.count()
            shares = getattr(content, "shares_count", 0)

            # Normalize metrics
            avg_views = self._get_average_metric("views")
            avg_likes = self._get_average_metric("likes")
            avg_comments = self._get_average_metric("comments")
            avg_shares = self._get_average_metric("shares")

            # Avoid division by zero
            avg_views = max(1, avg_views)
            avg_likes = max(1, avg_likes)
            avg_comments = max(1, avg_comments)
            avg_shares = max(1, avg_shares)

            # Calculate relative performance (compared to average)
            relative_views = min(5, views / avg_views)  # Cap at 5x average
            relative_likes = min(5, likes / avg_likes)
            relative_comments = min(5, comments / avg_comments)
            relative_shares = min(5, shares / avg_shares)

            # Weighted sum with log transformation to reduce extreme values
            score = (
                np.log1p(relative_views) * 0.2
                + np.log1p(relative_likes) * 0.4
                + np.log1p(relative_comments) * 0.3
                + np.log1p(relative_shares) * 0.1
            ) / np.log1p(
                5
            )  # Normalize to 0-1 range

            # Cache the result
            cache.set(cache_key, score, self.POPULARITY_CACHE_TTL)

            return score

        except Exception as e:
            logger.error(f"Error calculating popularity score: {e}")
            return 0.5  # Default middle score

    def _get_average_metric(self, metric_name):
        """
        Get the average value for a metric across all content
        Uses caching to avoid frequent recalculation
        """
        cache_key = f"avg_metric:{metric_name}"
        avg_value = cache.get(cache_key)

        if avg_value is None:
            # Calculate average based on metric
            if metric_name == "views":
                avg_value = ReelView.objects.count() / max(1, Reel.objects.count())
            elif metric_name == "likes":
                avg_value = ReelLike.objects.count() / max(1, Reel.objects.count())
            elif metric_name == "comments":
                avg_value = ReelComment.objects.count() / max(1, Reel.objects.count())
            elif metric_name == "shares":
                # If you track shares
                avg_value = 1  # Default if not tracking
            else:
                avg_value = 1

            # Cache the result
            cache.set(cache_key, avg_value, 60 * 60)  # 1 hour TTL

        return avg_value

    def _calculate_relevance_score(self, content, preferred_categories):
        """
        Calculate how relevant the content is to the user based on category preferences
        """
        if not preferred_categories:
            return 0.5  # Neutral score if no preferences

        content_category_id = getattr(content, "category_id", None)
        if not content_category_id and hasattr(content, "service") and content.service:
            content_category_id = content.service.category_id

        if not content_category_id:
            return 0.5  # Neutral score if no category

        # Direct category match
        if content_category_id in preferred_categories:
            return 1.0

        # Get parent/child categories for hierarchical matching
        try:
            category = Category.objects.get(id=content_category_id)
            if category.parent_id and category.parent_id in preferred_categories:
                return 0.8  # Parent category match

            # Check if this is a parent of any preferred categories
            child_categories = Category.objects.filter(parent_id=content_category_id)
            child_ids = set(child_categories.values_list("id", flat=True))
            if any(cat_id in child_ids for cat_id in preferred_categories):
                return 0.8  # Child category match
        except Exception as e:
            logger.error(f"Error in category relevance calculation: {e}")

        # No match
        return 0.3

    def _calculate_engagement_score(self, content, liked_content_ids, commented_content_ids):
        """
        Calculate an engagement score based on the user's past interactions
        """
        # Direct engagement with this content
        if content.id in liked_content_ids and content.id in commented_content_ids:
            return 1.0  # Maximum score for content user both liked and commented
        elif content.id in liked_content_ids:
            return 0.8  # High score for liked content
        elif content.id in commented_content_ids:
            return 0.9  # Very high score for commented content

        # No direct engagement
        return 0.5

    def _get_user_preferred_categories(self, customer):
        """
        Analyze user interactions to determine preferred categories
        Returns set of category IDs
        """
        # Look at views, likes, bookings to determine preferences
        liked_content = ReelLike.objects.filter(customer=customer)
        liked_content_with_categories = liked_content.select_related("reel__service__category")

        # Extract categories from liked content
        category_ids = set()
        for like in liked_content_with_categories:
            try:
                if like.reel.service and like.reel.service.category:
                    category_ids.add(like.reel.service.category_id)
            except Exception:
                pass

        # Also consider booked services
        from apps.bookingapp.models import Appointment

        booked_services = Appointment.objects.filter(customer=customer).select_related(
            "service__category"
        )

        for booking in booked_services:
            try:
                if booking.service and booking.service.category:
                    category_ids.add(booking.service.category_id)
            except Exception:
                pass

        return category_ids

    def _get_user_preferred_shops(self, customer):
        """
        Determine shops the user prefers based on interactions
        Returns set of shop IDs
        """
        # Explicitly followed shops
        followed_shops = set(
            Follow.objects.filter(customer=customer).values_list("shop_id", flat=True)
        )

        # Shops where user booked services
        from apps.bookingapp.models import Appointment

        booked_shops = set(
            Appointment.objects.filter(customer=customer).values_list("service__shop_id", flat=True)
        )

        # Combine all preferred shops
        preferred_shops = followed_shops.union(booked_shops)

        return preferred_shops

    def _get_nearby_content(self, location, limit=40):
        """
        Get content from nearby shops with distance calculation
        """
        # Limit to same city for efficiency
        city_content = (
            Reel.objects.filter(shop__location__city=location.city, is_active=True)
            .select_related("shop", "shop__location")
            .order_by("-created_at")[: limit * 2]
        )

        # Calculate distances
        content_with_distance = []
        for reel in city_content:
            try:
                shop_location = reel.shop.location
                if not shop_location:
                    continue

                # Calculate distance
                distance = self._calculate_distance(
                    location.latitude,
                    location.longitude,
                    shop_location.latitude,
                    shop_location.longitude,
                )

                content_with_distance.append({"content": reel, "distance": distance})
            except Exception as e:
                logger.error(f"Error calculating distance: {e}")

        # Sort by distance
        content_with_distance.sort(key=lambda x: x["distance"])

        return content_with_distance[:limit]

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two points using Haversine formula
        Returns distance in kilometers
        """
        from math import atan2, cos, radians, sin, sqrt

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Radius of Earth in kilometers
        radius = 6371

        # Distance in kilometers
        distance = radius * c

        return distance

    def _generate_fallback_feed(self, limit, offset):
        """
        Generate a basic feed as fallback if algorithmic approach fails
        """
        # Simple recency-based feed
        recent_content = Reel.objects.filter(is_active=True).order_by("-created_at")[
            offset : offset + limit
        ]

        # Add basic scoring
        scored_content = []
        for reel in recent_content:
            recency_score = self._calculate_recency_score(reel.created_at)

            scored_content.append(
                {
                    "content": reel,
                    "score": recency_score,
                    "components": {"recency": recency_score},
                }
            )

        return scored_content

    def _log_recommendations(self, customer, recommendations, feed_type):
        """
        Log recommendation details for analysis and improvement
        """
        try:
            import json

            log_data = {
                "timestamp": datetime.now().isoformat(),
                "customer_id": str(customer.id),
                "feed_type": feed_type,
                "recommendations": [
                    {
                        "content_id": str(item["content"].id),
                        "content_type": item["content"].__class__.__name__,
                        "score": item["score"],
                        "components": item.get("components", {}),
                    }
                    for item in recommendations[:5]
                ],  # Log top 5 only
            }

            logger.info(f"RECOMMENDATION_LOG: {json.dumps(log_data)}")
        except Exception as e:
            logger.error(f"Error logging recommendations: {e}")

    def update_similarity_matrix(self):
        """
        Periodically update the content similarity matrix
        This is a computationally expensive operation that should be run as a background task
        """
        # This would be implemented with a more sophisticated approach
        # such as collaborative filtering with matrix factorization
        pass
