import logging
from collections import defaultdict

from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.utils import timezone

from algorithms.recommendation.content_ranker import (
    collaborative_filtering_boost,
    diversity_reranker,
    weighted_content_ranking,
)
from apps.customersapp.models import CustomerPreference
from apps.followapp.services.follow_service import FollowService

from ..models import Reel, ReelLike, ReelView

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Advanced service for generating personalized reel recommendations
    Uses sophisticated algorithms to identify content most likely to engage a user
    """

    @staticmethod
    def get_recommended_reels(user_id, city=None, limit=20, diversity_level="medium"):
        """
        Get recommended reels for a user based on their preferences and behavior

        Args:
            user_id: UUID of the user
            city: City to filter by (optional)
            limit: Maximum number of recommendations to return
            diversity_level: How diverse the recommendations should be ('low', 'medium', 'high')

        Returns:
            QuerySet of Reel objects in recommended order
        """
        # Start with published reels
        queryset = Reel.objects.filter(status="published")

        # Filter by city if provided
        if city:
            queryset = queryset.filter(city=city)

        try:
            # Get user's category preferences
            category_preferences = {}
            customer_preferences = CustomerPreference.objects.filter(
                customer__user_id=user_id, preference_type="category"
            )

            for pref in customer_preferences:
                category_preferences[str(pref.category_id)] = pref.weight

            # Get user's viewing history, likes and follows
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Prepare for collaborative filtering
            user_interactions = RecommendationService._get_user_interactions(user_id)
            similar_users = RecommendationService._find_similar_users(user_id, city)

            # Use complex algorithm for recommendations
            # Get reels the user hasn't seen recently
            viewed_reel_ids = list(
                user.reel_views.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).values_list("reel_id", flat=True)
            )

            # Prioritize unseen content but include some popular seen content too
            reels_to_rank = list(queryset.exclude(id__in=viewed_reel_ids))

            # If we have few unseen reels, add some seen ones that were popular
            if len(reels_to_rank) < limit:
                popular_seen_reels = (
                    queryset.filter(id__in=viewed_reel_ids)
                    .annotate(
                        engagement=Count("likes")
                        + Count("comments") * 2
                        + Count("shares") * 3
                    )
                    .order_by("-engagement")[: limit - len(reels_to_rank)]
                )
                reels_to_rank.extend(popular_seen_reels)

            # If still no reels, return empty queryset
            if not reels_to_rank:
                return Reel.objects.none()

            # Prepare data for ranking algorithm
            reels_data = []
            reels_attributes = {}  # For diversity enforcement

            for reel in reels_to_rank:
                # Get reel category IDs
                category_ids = list(reel.categories.values_list("id", flat=True))

                # Calculate freshness factor (newer is better)
                days_old = (timezone.now() - reel.created_at).days
                freshness = max(
                    0, 1 - (days_old / 30.0)
                )  # 1.0 (new) to 0.0 (30+ days old)

                # Calculate engagement score
                engagement = (
                    reel.likes.count()
                    + (reel.comments.count() * 2)
                    + (reel.shares.count() * 3)
                ) / max(
                    1, reel.view_count
                )  # Avoid division by zero

                # Prepare attributes for diversity calculation
                attributes = []
                attributes.extend([f"category:{cid}" for cid in category_ids])
                attributes.append(f"shop:{reel.shop_id}")
                if reel.services.exists():
                    attributes.extend(
                        [
                            f"service:{sid}"
                            for sid in reel.services.values_list("id", flat=True)
                        ]
                    )

                reels_attributes[str(reel.id)] = attributes

                reels_data.append(
                    {
                        "id": str(reel.id),
                        "category_ids": [str(cid) for cid in category_ids],
                        "shop_id": str(reel.shop_id),
                        "engagement_score": engagement,
                        "freshness": freshness,
                        "created_at": reel.created_at,
                        "has_viewed": str(reel.id) in viewed_reel_ids,
                    }
                )

            # Apply collaborative filtering if we have similar users
            if similar_users and user_interactions:
                reels_data = collaborative_filtering_boost(
                    reels_data,
                    str(user_id),
                    similar_users,
                    user_interactions,
                    boost_factor=0.4,
                )

            # Set weights based on user's profile
            has_preferences = bool(category_preferences)
            viewing_history = user.reel_views.count() > 10

            # Determine optimal weights based on user profile
            if has_preferences and viewing_history:
                # Experienced user with preferences - balanced approach
                content_freshness_weight = 0.2
                content_engagement_weight = 0.3
                category_match_weight = 0.35
                diversity_weight = 0.15
            elif has_preferences:
                # New user with preferences - focus on matching preferences
                content_freshness_weight = 0.2
                content_engagement_weight = 0.2
                category_match_weight = 0.5
                diversity_weight = 0.1
            elif viewing_history:
                # Experienced user without preferences - focus on engagement and diversity
                content_freshness_weight = 0.25
                content_engagement_weight = 0.4
                category_match_weight = 0.15
                diversity_weight = 0.2
            else:
                # New user without preferences - balanced default
                content_freshness_weight = 0.25
                content_engagement_weight = 0.35
                category_match_weight = 0.2
                diversity_weight = 0.2

            # Adjust diversity level based on parameter
            diversity_settings = {"low": 0.1, "medium": 0.2, "high": 0.3}
            diversity_weight = diversity_settings.get(diversity_level, diversity_weight)

            # Use the recommendation algorithm to rank reels
            ranked_reel_ids = weighted_content_ranking(
                reels_data,
                category_preferences,
                content_freshness_weight=content_freshness_weight,
                content_engagement_weight=content_engagement_weight,
                category_match_weight=category_match_weight,
                diversity_weight=diversity_weight,
            )

            # Apply diversity reranking
            ranked_reel_ids = diversity_reranker(
                ranked_reel_ids,
                reels_attributes,
                diversity_threshold=diversity_weight,  # Use same weight for consistency
            )

            # Reorder queryset based on recommendation ranking
            if ranked_reel_ids:
                # Create a Case statement for ordering
                preserved_order = Case(
                    *[
                        When(id=pk, then=Value(i))
                        for i, pk in enumerate(ranked_reel_ids)
                    ],
                    output_field=IntegerField(),
                )

                # Return queryset in the calculated order
                return (
                    queryset.filter(id__in=ranked_reel_ids)
                    .annotate(custom_order=preserved_order)
                    .order_by("custom_order")[:limit]
                )

            # Fallback if algorithm fails
            return queryset.annotate(
                engagement_score=(
                    Count("likes") + Count("comments") * 2 + Count("shares") * 3
                )
            ).order_by("-engagement_score", "-created_at")[:limit]

        except Exception as e:
            logger.error(f"Error in recommendation algorithm: {str(e)}")
            # Fall back to popularity-based recommendations
            return queryset.annotate(
                engagement_score=(
                    Count("likes") + Count("comments") * 2 + Count("shares") * 3
                )
            ).order_by("-engagement_score", "-created_at")[:limit]

    @staticmethod
    def _get_user_interactions(user_id):
        """Get a map of user interactions with reels for collaborative filtering"""
        try:
            # Get all reel views in the last 90 days
            views = ReelView.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=90)
            ).select_related("user")

            # Get all reel likes
            likes = ReelLike.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=90)
            ).select_related("user")

            # Build interaction map
            interactions = defaultdict(list)

            # Add views (1x weight)
            for view in views:
                interactions[str(view.user_id)].append(str(view.reel_id))

            # Add likes (3x weight - count multiple times to increase importance)
            for like in likes:
                interactions[str(like.user_id)].extend([str(like.reel_id)] * 3)

            return dict(interactions)
        except Exception as e:
            logger.error(f"Error getting user interactions: {str(e)}")
            return {}

    @staticmethod
    def _find_similar_users(user_id, city=None):
        """Find users similar to the given user for collaborative filtering"""
        try:
            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Get the current user
            user = User.objects.get(id=user_id)
            if not hasattr(user, "customer"):
                return []

            customer = user.customer

            # Find similar users based on multiple factors
            similar_users = []

            # 1. Category preferences similarity
            user_categories = set(
                CustomerPreference.objects.filter(
                    customer=customer, preference_type="category"
                ).values_list("category_id", flat=True)
            )

            if user_categories:
                # Find users with similar category preferences
                similar_by_category = (
                    CustomerPreference.objects.filter(
                        preference_type="category", category_id__in=user_categories
                    )
                    .exclude(customer=customer)
                    .values("customer__user_id")
                    .annotate(matches=Count("category_id"))
                    .order_by("-matches")[:50]
                )

                # Convert to format: (user_id, similarity_score)
                max_possible = max(len(user_categories), 1)
                for item in similar_by_category:
                    similarity = item["matches"] / max_possible
                    similar_users.append(
                        (
                            str(item["customer__user_id"]),
                            similarity * 0.4,  # Weight for category similarity
                        )
                    )

            # 2. Similar follow patterns
            following_shops = set(FollowService.get_following_shop_ids(customer))

            if following_shops:
                # Find customers who follow similar shops
                user_customers = CustomerPreference.objects.values_list(
                    "customer_id", flat=True
                ).distinct()
                similar_by_follows = []

                # This would be better as a database query, but for illustration:
                for other_customer_id in user_customers:
                    if other_customer_id == customer.id:
                        continue

                    # Get shops this customer follows
                    other_following = set(
                        FollowService.get_following_shop_ids_by_customer_id(
                            other_customer_id
                        )
                    )

                    # Calculate Jaccard similarity
                    if other_following:
                        intersection = len(
                            following_shops.intersection(other_following)
                        )
                        union = len(following_shops.union(other_following))
                        if union > 0:
                            similarity = intersection / union
                            if similarity > 0.1:  # Only consider significant similarity
                                other_user_id = (
                                    CustomerPreference.objects.filter(
                                        customer_id=other_customer_id
                                    )
                                    .values_list("customer__user_id", flat=True)
                                    .first()
                                )

                                if other_user_id:
                                    similar_by_follows.append(
                                        (
                                            str(other_user_id),
                                            similarity
                                            * 0.6,  # Weight for follow similarity (more important)
                                        )
                                    )

                # Sort by similarity and take top results
                similar_by_follows.sort(key=lambda x: x[1], reverse=True)
                similar_users.extend(similar_by_follows[:30])

            # 3. Similar city (lower weight)
            if city and hasattr(customer, "city") and customer.city:
                city_users = (
                    User.objects.filter(customer__city=customer.city)
                    .exclude(id=user_id)
                    .values_list("id", flat=True)[:50]
                )

                for other_user_id in city_users:
                    similar_users.append(
                        (str(other_user_id), 0.1)  # Small weight for city similarity
                    )

            # Combine and deduplicate similar users
            combined = {}
            for user_id, score in similar_users:
                if user_id not in combined:
                    combined[user_id] = 0
                combined[user_id] += score

            # Convert back to list and normalize
            result = [(user_id, score) for user_id, score in combined.items()]
            result.sort(key=lambda x: x[1], reverse=True)

            # Limit results and ensure scores are in 0-1 range
            result = result[:50]  # Keep top 50 similar users
            if result:
                max_score = max(score for _, score in result)
                if max_score > 0:
                    result = [
                        (user_id, min(score / max_score, 1.0))
                        for user_id, score in result
                    ]

            return result

        except Exception as e:
            logger.error(f"Error finding similar users: {str(e)}")
            return []

    @staticmethod
    def get_similar_reels(reel_id, limit=10):
        """
        Get reels similar to the given reel

        Args:
            reel_id: UUID of the reference reel
            limit: Maximum number of similar reels to return

        Returns:
            QuerySet of Reel objects similar to the reference reel
        """
        try:
            # Get the reference reel
            reference_reel = Reel.objects.get(id=reel_id)

            # Get category IDs and shop ID from reference reel
            category_ids = reference_reel.categories.values_list("id", flat=True)
            shop_id = reference_reel.shop_id
            service_ids = reference_reel.services.values_list("id", flat=True)

            # Find reels with similar characteristics
            similar_reels = Reel.objects.filter(status="published").exclude(id=reel_id)

            # Apply filters to narrow down potential matches
            if category_ids:
                similar_reels = similar_reels.filter(categories__id__in=category_ids)

            if service_ids:
                similar_reels = similar_reels.filter(services__id__in=service_ids)

            # Annotate with similarity score components
            similar_reels = similar_reels.annotate(
                # Same shop bonus
                is_same_shop=Case(
                    When(shop_id=shop_id, then=Value(3)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                # Category match count
                matching_categories=Count(
                    "categories",
                    filter=Q(categories__id__in=category_ids),
                    distinct=True,
                ),
                # Service match count
                matching_services=Count(
                    "services", filter=Q(services__id__in=service_ids), distinct=True
                ),
                # Content age similarity (smaller time gap is better)
                time_similarity=Case(
                    When(
                        created_at__gte=reference_reel.created_at
                        - timezone.timedelta(days=30),
                        created_at__lte=reference_reel.created_at
                        + timezone.timedelta(days=30),
                        then=Value(2),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )

            # Calculate total similarity score with different weights
            similar_reels = similar_reels.annotate(
                similarity_score=(
                    F("is_same_shop") * 1.0  # Shop match (weight: 1.0)
                    + F("matching_categories") * 1.5  # Category match (weight: 1.5)
                    + F("matching_services") * 2.0  # Service match (weight: 2.0)
                    + F("time_similarity") * 0.5  # Time similarity (weight: 0.5)
                )
            )

            # Order by similarity score, then by engagement and recency
            similar_reels = (
                similar_reels.annotate(
                    engagement=(
                        Count("likes") + Count("comments") * 2 + Count("shares") * 3
                    )
                )
                .order_by("-similarity_score", "-engagement", "-created_at")
                .distinct()[:limit]
            )

            return similar_reels

        except Exception as e:
            logger.error(f"Error finding similar reels: {str(e)}")
            # Fall back to general recommendations
            return Reel.objects.filter(status="published").order_by("-created_at")[
                :limit
            ]
