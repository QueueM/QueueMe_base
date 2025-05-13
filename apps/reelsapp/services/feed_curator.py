from django.contrib.auth import get_user_model
from django.db.models import Case, Count, IntegerField, Value, When
from django.utils import timezone

from apps.customersapp.models import CustomerPreference
from apps.followapp.models import Follow
from apps.geoapp.services.distance_service import DistanceService
from apps.shopapp.models import Shop

from ..models import Reel

User = get_user_model()


class FeedCuratorService:
    """Advanced service for curating personalized reel feeds"""

    @staticmethod
    def get_nearby_feed(user_id, city=None, location=None):
        """
        Get reels from the same city as the user, sorted by distance

        Args:
            user_id: UUID of the user requesting the feed
            city: City to filter by (optional, will use user's city if not provided)
            location: Dictionary with latitude and longitude (optional)
                      Example: {'latitude': 24.774265, 'longitude': 46.738586}

        Returns:
            QuerySet of Reel objects
        """
        # Start with published reels
        queryset = Reel.objects.filter(status="published")

        # Filter by city if provided
        if city:
            queryset = queryset.filter(city=city)

        # Add engagement metrics for sorting
        queryset = queryset.annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count("comments", distinct=True),
            shares_count=Count("shares", distinct=True),
        )

        # If location provided, order by distance
        if location and location.get("latitude") and location.get("longitude"):
            # Get shop locations
            shop_ids = queryset.values_list("shop_id", flat=True).distinct()
            shops = Shop.objects.filter(id__in=shop_ids)

            # Calculate distances
            shop_distances = {}
            for shop in shops:
                if shop.location:
                    shop_location = {
                        "latitude": shop.location.latitude,
                        "longitude": shop.location.longitude,
                    }
                    distance = DistanceService.calculate_distance(location, shop_location)
                    shop_distances[str(shop.id)] = distance

            # Order queryset based on distances
            # This is a complex operation - we're adding a distance annotation
            # then ordering by it

            # First, get the IDs in the order we want
            ordered_shop_ids = sorted(shop_distances.keys(), key=lambda x: shop_distances[x])

            # Then use Case/When to order the queryset
            case_statement = Case(
                *[When(shop_id=pk, then=Value(i)) for i, pk in enumerate(ordered_shop_ids)],
                default=Value(len(ordered_shop_ids)),
                output_field=IntegerField()
            )

            queryset = queryset.annotate(distance_order=case_statement).order_by("distance_order")
        else:
            # Default ordering if no location
            queryset = queryset.order_by("-created_at")

        # Ensure we don't have duplicates
        return queryset.distinct()

    @staticmethod
    def get_personalized_feed(user_id, city=None):
        """
        Get personalized "For You" feed based on user's preferences and engagement

        Args:
            user_id: UUID of the user requesting the feed
            city: City to filter by (optional, will use user's city if not provided)

        Returns:
            QuerySet of Reel objects
        """
        # Start with published reels
        queryset = Reel.objects.filter(status="published")

        # Filter by city if provided
        if city:
            queryset = queryset.filter(city=city)

        # Get user's engagement history
        user = User.objects.get(id=user_id)

        # Get services user has booked or viewed
        booked_service_ids = set()
        if hasattr(user, "appointments"):
            booked_service_ids = set(
                user.appointments.values_list("service_id", flat=True).distinct()
            )

        # Get categories user has shown interest in
        category_ids = set()
        try:
            if hasattr(user, "customer") and hasattr(user.customer, "preferences"):
                category_preferences = CustomerPreference.objects.filter(
                    customer=user.customer, preference_type="category"
                )
                category_ids = set(
                    category_preferences.values_list("category_id", flat=True).distinct()
                )
        except Exception:
            # If customer preferences are not accessible, continue without them
            pass

        # Get shops user has interacted with
        liked_reel_shop_ids = set(
            user.reel_likes.values_list("reel__shop_id", flat=True).distinct()
        )

        commented_reel_shop_ids = set(
            user.reel_comments.values_list("reel__shop_id", flat=True).distinct()
        )

        viewed_reel_shop_ids = set(
            user.reel_views.values_list("reel__shop_id", flat=True).distinct()
        )

        interacted_shop_ids = liked_reel_shop_ids.union(
            commented_reel_shop_ids, viewed_reel_shop_ids
        )

        # Calculate relevance score based on different factors
        rankings = []

        for reel in queryset:
            score = 0

            # Engagement factor - reels with higher engagement get higher score
            engagement_score = reel.get_engagement_score()
            score += min(engagement_score / 10, 10)  # Cap at 10 points

            # Recency factor - newer reels get higher score
            days_old = (timezone.now() - reel.created_at).days
            recency_score = max(10 - (days_old / 2), 0)  # Newer = higher score, 0 after 20 days
            score += recency_score

            # Service match - if reel features services user has booked
            if any(
                service_id in booked_service_ids
                for service_id in reel.services.values_list("id", flat=True)
            ):
                score += 5

            # Category match - if reel is in categories user is interested in
            if any(
                category_id in category_ids
                for category_id in reel.categories.values_list("id", flat=True)
            ):
                score += 3

            # Shop interaction - if user has interacted with this shop before
            if str(reel.shop_id) in interacted_shop_ids:
                score += 3

            rankings.append((reel, score))

        # Sort by score (descending)
        rankings.sort(key=lambda x: x[1], reverse=True)

        # Get reel IDs in the ranked order
        reel_ids = [reel.id for reel, _ in rankings]

        # Requery to get a proper queryset in the correct order
        if reel_ids:
            # Create a Case statement for ordering
            preserved_order = Case(
                *[When(id=pk, then=Value(i)) for i, pk in enumerate(reel_ids)],
                output_field=IntegerField()
            )

            # Return queryset in the calculated order
            return (
                queryset.filter(id__in=reel_ids)
                .annotate(custom_order=preserved_order)
                .order_by("custom_order")
            )

        # Fallback to default ordering if no reels found
        return queryset.order_by("-created_at")

    @staticmethod
    def get_following_feed(user_id):
        """
        Get reels from shops the user follows

        Args:
            user_id: UUID of the user requesting the feed

        Returns:
            QuerySet of Reel objects
        """
        # Get shops user is following
        followed_shop_ids = Follow.objects.filter(user_id=user_id, is_active=True).values_list(
            "shop_id", flat=True
        )

        # Get reels from followed shops
        queryset = Reel.objects.filter(status="published", shop_id__in=followed_shop_ids)

        # Add engagement metrics
        queryset = queryset.annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count("comments", distinct=True),
            shares_count=Count("shares", distinct=True),
        )

        # Order by most recent
        return queryset.order_by("-created_at")
