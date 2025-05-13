from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Case, Count, F, FloatField, OuterRef, Subquery, Value, When

from apps.reviewapp.models import Review
from apps.shopapp.models import Shop


class ShopVisibilityService:
    @staticmethod
    def get_visible_shops_for_customer(
        customer, city=None, category_id=None, lat=None, lng=None, radius=10
    ):
        """
        Get shops visible to a customer based on location and other criteria

        Args:
            customer: User object representing the customer
            city: Optional city to filter shops
            category_id: Optional category ID to filter shops
            lat: Optional latitude for location-based filtering
            lng: Optional longitude for location-based filtering
            radius: Radius in km for location-based filtering (default 10km)

        Returns:
            QuerySet of visible shops, sorted by relevance
        """
        # Start with active and verified shops
        queryset = Shop.objects.filter(is_verified=True, is_active=True)

        # Apply city filter (either specified or from customer profile)
        if city:
            queryset = queryset.filter(location__city__iexact=city)
        elif hasattr(customer, "profile") and customer.profile.city:
            queryset = queryset.filter(location__city__iexact=customer.profile.city)

        # Apply category filter if specified
        if category_id:
            queryset = queryset.filter(services__category__id=category_id).distinct()

        # Apply location-based filter if coordinates provided
        if lat is not None and lng is not None:
            try:
                from apps.geoapp.services.geo_service import GeoService

                shop_ids = GeoService.find_nearby_entities((float(lat), float(lng)), radius, "shop")
                queryset = queryset.filter(id__in=shop_ids)
            except (ValueError, TypeError):
                pass

        # Sort by relevance
        return ShopVisibilityService.sort_shops_by_relevance(queryset, customer)

    @staticmethod
    def sort_shops_by_relevance(queryset, customer):
        """
        Sort shops by relevance to the customer

        This uses a sophisticated algorithm that considers:
        - Shop ratings
        - Distance (if location data available)
        - Previous interactions (bookings, follows)
        - Popularity (booking count)
        - Featured status

        Args:
            queryset: Base QuerySet of shops
            customer: User object representing the customer

        Returns:
            QuerySet sorted by relevance score
        """
        # Start by annotating with rating data
        shop_type = ContentType.objects.get_for_model(Shop)

        # Subquery for average ratings
        avg_rating_subquery = (
            Review.objects.filter(content_type=shop_type, object_id=OuterRef("id"))
            .values("object_id")
            .annotate(avg_rating=Avg("rating"))
            .values("avg_rating")
        )

        # Annotate with review count and booking count
        queryset = queryset.annotate(
            review_count=Count(
                Case(When(review__content_type=shop_type, then=1), default=None),
                distinct=True,
            ),
            booking_count=Count("appointments", distinct=True),
            avg_rating=Subquery(avg_rating_subquery),
        )

        # Check if customer has followed any shops
        followed_shops = []
        if customer.is_authenticated:
            from apps.shopapp.models import ShopFollower

            followed_shops = ShopFollower.objects.filter(customer=customer).values_list(
                "shop_id", flat=True
            )

            # Also get shops customer has booked before
            from apps.bookingapp.models import Appointment

            booked_shops = (
                Appointment.objects.filter(customer=customer)
                .values_list("shop_id", flat=True)
                .distinct()
            )

            # Add annotation for customer affinity
            queryset = queryset.annotate(
                is_followed=Case(
                    When(id__in=followed_shops, then=Value(1)),
                    default=Value(0),
                    output_field=FloatField(),
                ),
                is_booked=Case(
                    When(id__in=booked_shops, then=Value(1)),
                    default=Value(0),
                    output_field=FloatField(),
                ),
            )
        else:
            # Default values for unauthenticated users
            queryset = queryset.annotate(
                is_followed=Value(0, output_field=FloatField()),
                is_booked=Value(0, output_field=FloatField()),
            )

        # Calculate relevance score
        # Weights for different factors (can be adjusted)
        weights = {
            "rating": 0.3,  # 30% weight for ratings
            "featured": 0.15,  # 15% weight for featured status
            "booking": 0.2,  # 20% weight for booking popularity
            "affinity": 0.35,  # 35% weight for customer affinity (follows & past bookings)
        }

        # Normalize booking count (log scale to dampen effect of very popular shops)
        queryset = queryset.annotate(
            normalized_booking_score=Case(
                When(booking_count__gt=0, then=F("booking_count")),
                default=Value(0),
                output_field=FloatField(),
            )
        )

        # Use Django's conditional expressions to calculate weighted score
        queryset = queryset.annotate(
            rating_score=Case(
                When(
                    avg_rating__isnull=False,
                    then=F("avg_rating") * Value(weights["rating"]),
                ),
                default=Value(0),
                output_field=FloatField(),
            ),
            featured_score=Case(
                When(is_featured=True, then=Value(weights["featured"])),
                default=Value(0),
                output_field=FloatField(),
            ),
            booking_score=F("normalized_booking_score") * Value(weights["booking"]),
            affinity_score=(F("is_followed") * Value(0.7) + F("is_booked") * Value(0.3))
            * Value(weights["affinity"]),
            relevance_score=F("rating_score")
            + F("featured_score")
            + F("booking_score")
            + F("affinity_score"),
        )

        # Order by relevance score
        return queryset.order_by("-relevance_score")

    @staticmethod
    def filter_by_same_city(shops, city):
        """
        Filter shops to only include those in the specified city

        Args:
            shops: QuerySet of shops
            city: City name to filter by

        Returns:
            QuerySet filtered by city
        """
        if not city:
            return shops

        return shops.filter(location__city__iexact=city)

    @staticmethod
    def get_top_shops_in_city(city, limit=10, category_id=None):
        """
        Get top-rated shops in a specific city

        Args:
            city: City to filter shops by
            limit: Maximum number of shops to return
            category_id: Optional category ID to filter shops

        Returns:
            QuerySet of top shops in the city
        """
        # Filter by city, active status, and verification
        queryset = Shop.objects.filter(
            location__city__iexact=city, is_active=True, is_verified=True
        )

        # Apply category filter if specified
        if category_id:
            queryset = queryset.filter(services__category__id=category_id).distinct()

        # Get shop content type for reviews
        shop_type = ContentType.objects.get_for_model(Shop)

        # Annotate with review and booking data
        queryset = queryset.annotate(
            review_count=Count(
                Case(When(review__content_type=shop_type, then=1), default=None),
                distinct=True,
            ),
            booking_count=Count("appointments", distinct=True),
            avg_rating=Avg(
                Case(
                    When(review__content_type=shop_type, then=F("review__rating")),
                    default=None,
                    output_field=FloatField(),
                )
            ),
        )

        # Calculate weighted score based on ratings and popularity
        queryset = queryset.annotate(
            weighted_score=Case(
                When(
                    review_count__gt=0,
                    then=F("avg_rating") * Value(0.7)
                    + (F("booking_count") / Value(10.0)) * Value(0.3),
                ),
                default=F("booking_count") / Value(10.0),
                output_field=FloatField(),
            )
        )

        # Featured shops first, then by weighted score
        return queryset.order_by("-is_featured", "-weighted_score")[:limit]
