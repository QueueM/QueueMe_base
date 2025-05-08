import logging

from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.utils import timezone

from algorithms.recommendation.content_ranker import weighted_content_ranking
from apps.customersapp.models import CustomerPreference

from ..models import Reel

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Advanced service for generating personalized reel recommendations
    Uses machine learning techniques to identify content most likely to engage a user
    """

    @staticmethod
    def get_recommended_reels(user_id, city=None, limit=20):
        """
        Get recommended reels for a user based on their preferences and behavior

        Args:
            user_id: UUID of the user
            city: City to filter by (optional)
            limit: Maximum number of recommendations to return

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

            # Get user's viewing history
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Use complex algorithm for recommendations if user has preferences
            if category_preferences:
                # Get reels the user hasn't seen yet
                viewed_reel_ids = user.reel_views.values_list("reel_id", flat=True)
                reels_to_rank = queryset.exclude(id__in=viewed_reel_ids)

                # If no unseen reels, fall back to all reels
                if not reels_to_rank.exists():
                    reels_to_rank = queryset

                # Prepare data for ranking algorithm
                reels_data = []
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

                    reels_data.append(
                        {
                            "id": str(reel.id),
                            "category_ids": [str(cid) for cid in category_ids],
                            "shop_id": str(reel.shop_id),
                            "engagement_score": engagement,
                            "freshness": freshness,
                        }
                    )

                # Use the recommendation algorithm to rank reels
                ranked_reel_ids = weighted_content_ranking(
                    reels_data,
                    category_preferences,
                    content_freshness_weight=0.3,
                    content_engagement_weight=0.3,
                    category_match_weight=0.4,
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

            # Fallback if user has no preferences or algorithm fails
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

            # Find reels with similar categories
            similar_reels = Reel.objects.filter(
                status="published", categories__id__in=category_ids
            ).exclude(id=reel_id)

            # Annotate with similarity score
            # - Same shop: +3 points
            # - Each matching category: +1 point
            similar_reels = similar_reels.annotate(
                is_same_shop=Case(
                    When(shop_id=shop_id, then=Value(3)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                matching_categories=Count(
                    "categories", filter=Q(categories__id__in=category_ids)
                ),
            )

            # Calculate total similarity score
            similar_reels = similar_reels.annotate(
                similarity_score=F("is_same_shop") + F("matching_categories")
            )

            # Order by similarity score, then by engagement and recency
            return similar_reels.order_by(
                "-similarity_score", "-created_at"
            ).distinct()[:limit]

        except Exception as e:
            logger.error(f"Error finding similar reels: {str(e)}")
            # Fall back to general recommendations
            return Reel.objects.filter(status="published").order_by("-created_at")[
                :limit
            ]
