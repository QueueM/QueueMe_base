from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.specialistsapp.constants import SPECIALIST_RECOMMENDATIONS_CACHE_KEY
from apps.specialistsapp.models import Specialist


class SpecialistRecommender:
    """
    Advanced recommendation service using customer behavior and preferences
    to suggest the most relevant specialists.
    """

    def get_recommendations(self, customer, category_id=None, limit=5):
        """
        Get personalized specialist recommendations for a customer.

        Args:
            customer: User object of the customer
            category_id: Optional UUID of category to filter recommendations
            limit: Maximum number of specialists to recommend

        Returns:
            QuerySet of recommended specialists
        """
        # Try to get from cache first
        cache_key = SPECIALIST_RECOMMENDATIONS_CACHE_KEY.format(
            customer_id=customer.id, category_id=category_id or "all"
        )

        cached_results = cache.get(cache_key)
        if cached_results:
            return cached_results

        # Get customer city
        customer_profile = getattr(customer, "customer_profile", None)
        customer_city = getattr(customer_profile, "city", None)

        # Base queryset - active specialists in customer's city if known
        queryset = Specialist.objects.filter(
            employee__is_active=True, employee__shop__is_active=True
        )

        if customer_city:
            queryset = queryset.filter(employee__shop__location__city=customer_city)

        # Apply category filter if provided
        if category_id:
            queryset = queryset.filter(
                Q(expertise__id=category_id)
                | Q(specialist_services__service__category_id=category_id)
            ).distinct()

        # Get customer's booking history
        from apps.bookingapp.models import Appointment

        past_bookings = Appointment.objects.filter(
            customer=customer, status__in=["completed", "cancelled", "no_show"]
        ).select_related("service", "specialist", "shop")

        # If no booking history, return top-rated specialists
        if not past_bookings.exists():
            from apps.specialistsapp.services.specialist_ranker import SpecialistRanker

            ranker = SpecialistRanker()
            recommendations = ranker.get_top_rated_specialists(queryset, limit)

            # Cache for 1 hour
            cache.set(cache_key, recommendations, 60 * 60)

            return recommendations

        # Extract customer preferences from booking history
        booked_specialists = set(
            booking.specialist_id
            for booking in past_bookings
            if booking.specialist_id is not None
        )

        booked_services = set(booking.service_id for booking in past_bookings)

        booked_shops = set(booking.shop_id for booking in past_bookings)

        booked_categories = set(
            booking.service.category_id
            for booking in past_bookings
            if booking.service.category_id is not None
        )

        # Get customer reviews
        from django.contrib.contenttypes.models import ContentType

        from apps.reviewapp.models import Review

        specialist_type = ContentType.objects.get(
            app_label="specialistsapp", model="specialist"
        )

        customer_reviews = Review.objects.filter(
            created_by=customer, content_type=specialist_type
        )

        # Get highly rated specialists from customer reviews
        positively_reviewed = set(
            review.object_id for review in customer_reviews if review.rating >= 4
        )

        negatively_reviewed = set(
            review.object_id for review in customer_reviews if review.rating <= 2
        )

        # Build complex recommendation query with components

        # 1. Previously booked and liked specialists get highest weight
        queryset = queryset.annotate(
            previously_booked=Case(
                When(id__in=booked_specialists, then=Value(1)),
                default=Value(0),
                output_field=FloatField(),
            ),
            positively_reviewed=Case(
                When(id__in=positively_reviewed, then=Value(1)),
                default=Value(0),
                output_field=FloatField(),
            ),
            negatively_reviewed=Case(
                When(id__in=negatively_reviewed, then=Value(1)),
                default=Value(0),
                output_field=FloatField(),
            ),
        )

        # 2. Service similarity - specialists offering same services
        queryset = queryset.annotate(
            service_similarity=Count(
                "specialist_services__service",
                filter=Q(specialist_services__service__in=booked_services),
            )
        )

        # 3. Category similarity - specialists with same categories
        queryset = queryset.annotate(
            category_similarity=Count(
                "expertise", filter=Q(expertise__in=booked_categories)
            )
            + Count(
                "specialist_services__service__category",
                filter=Q(specialist_services__service__category__in=booked_categories),
            )
        )

        # 4. Shop familiarity - specialists from shops customer has visited
        queryset = queryset.annotate(
            same_shop=Case(
                When(employee__shop__in=booked_shops, then=Value(1)),
                default=Value(0),
                output_field=FloatField(),
            )
        )

        # Calculate final recommendation score
        queryset = queryset.annotate(
            recommendation_score=ExpressionWrapper(
                # Previously booked and reviewed
                (F("previously_booked") * 2.0)
                + (F("positively_reviewed") * 3.0)
                - (F("negatively_reviewed") * 10.0)  # Strong negative signal
                +
                # Service and category relevance
                (F("service_similarity") * 1.0) + (F("category_similarity") * 0.7) +
                # Shop familiarity
                (F("same_shop") * 0.5) +
                # General quality indicators
                (Coalesce(F("avg_rating"), 0) / 5.0 * 0.8)
                + (F("total_bookings") / 100.0 * 0.3)  # Normalize to 0-1 range
                +
                # Verification bonus
                Case(
                    When(is_verified=True, then=Value(0.5)),
                    default=Value(0),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            )
        )

        # Exclude negatively reviewed specialists (zero tolerance policy)
        queryset = queryset.filter(negatively_reviewed=0)

        # Get top recommendations based on score
        recommendations = queryset.order_by("-recommendation_score", "-avg_rating")[
            :limit
        ]

        # Cache for 1 hour
        cache.set(cache_key, recommendations, 60 * 60)

        return recommendations

    def get_specialist_similarity(self, specialist_id, limit=5):
        """
        Find specialists similar to ones a customer has already booked or liked.

        Args:
            specialist_id: UUID of the reference specialist
            limit: Maximum number of similar specialists to return

        Returns:
            QuerySet of similar specialists
        """
        from apps.specialistsapp.services.specialist_ranker import SpecialistRanker

        ranker = SpecialistRanker()
        return ranker.get_similar_specialists(specialist_id, limit)

    def get_personalized_top_specialists(self, customer, limit=10):
        """
        Get top specialists personalized for a customer based on their
        location, service history and preferences.

        Args:
            customer: User object of the customer
            limit: Maximum number of specialists to return

        Returns:
            QuerySet of personalized top specialists
        """
        # Get customer city
        customer_profile = getattr(customer, "customer_profile", None)
        customer_city = getattr(customer_profile, "city", None)

        # Base queryset - filter by city if known
        queryset = Specialist.objects.filter(
            employee__is_active=True, employee__shop__is_active=True, is_verified=True
        )

        if customer_city:
            queryset = queryset.filter(employee__shop__location__city=customer_city)

        # Get customer's booking history to extract preferences
        from apps.bookingapp.models import Appointment

        past_bookings = Appointment.objects.filter(
            customer=customer, status="completed"
        ).select_related("service", "service__category")

        # If customer has booking history, use it for personalization
        if past_bookings.exists():
            # Get booked categories and services
            booked_categories = set()
            booked_services = set()

            for booking in past_bookings:
                booked_services.add(booking.service_id)
                if booking.service.category_id:
                    booked_categories.add(booking.service.category_id)

            # Annotate with personalization factors
            queryset = queryset.annotate(
                # Service match
                service_match=Count(
                    "specialist_services__service",
                    filter=Q(specialist_services__service__in=booked_services),
                ),
                # Category match
                category_match=Count(
                    "specialist_services__service__category",
                    filter=Q(
                        specialist_services__service__category__in=booked_categories
                    ),
                )
                + Count("expertise", filter=Q(expertise__in=booked_categories)),
                # Personalized score combining standard ranking with preference match
                personalized_score=ExpressionWrapper(
                    # Standard quality indicators
                    (Coalesce(F("avg_rating"), 0) / 5.0 * 0.4)
                    + (F("total_bookings") / 100.0 * 0.2)
                    +
                    # Preference match indicators
                    (F("service_match") * 0.25) + (F("category_match") * 0.15),
                    output_field=FloatField(),
                ),
            )

            # Return specialists with personalized ranking
            return queryset.order_by("-personalized_score", "-avg_rating")[:limit]
        else:
            # No booking history, fall back to standard ranking
            from apps.specialistsapp.services.specialist_ranker import SpecialistRanker

            ranker = SpecialistRanker()
            return ranker.get_top_rated_specialists(queryset, limit)

    def recommend_new_specialists(self, customer, limit=5):
        """
        Recommend new specialists that the customer hasn't booked before,
        but might be interested in based on preferences.

        Args:
            customer: User object of the customer
            limit: Maximum number of specialists to recommend

        Returns:
            QuerySet of recommended new specialists
        """
        # Get customer's booking history
        from apps.bookingapp.models import Appointment

        past_specialist_ids = (
            Appointment.objects.filter(customer=customer)
            .values_list("specialist_id", flat=True)
            .distinct()
        )

        # Base queryset - exclude previously booked specialists
        queryset = Specialist.objects.filter(
            employee__is_active=True, employee__shop__is_active=True, is_verified=True
        ).exclude(id__in=past_specialist_ids)

        # Get customer city for location filtering
        customer_profile = getattr(customer, "customer_profile", None)
        customer_city = getattr(customer_profile, "city", None)

        if customer_city:
            queryset = queryset.filter(employee__shop__location__city=customer_city)

        # Extract customer preferences from booking history
        booked_services = (
            Appointment.objects.filter(customer=customer, status="completed")
            .values_list("service_id", flat=True)
            .distinct()
        )

        service_categories = set()
        from apps.serviceapp.models import Service

        for service_id in booked_services:
            try:
                service = Service.objects.get(id=service_id)
                if service.category_id:
                    service_categories.add(service.category_id)
            except Service.DoesNotExist:
                pass

        # If we have preference data, use it
        if service_categories:
            # Score specialists based on category match
            queryset = queryset.annotate(
                category_match=Count(
                    "expertise", filter=Q(expertise__id__in=service_categories)
                )
                + Count(
                    "specialist_services__service__category",
                    filter=Q(
                        specialist_services__service__category__id__in=service_categories
                    ),
                ),
                discovery_score=ExpressionWrapper(
                    # Quality indicators
                    (Coalesce(F("avg_rating"), 0) / 5.0 * 0.5)
                    + (F("total_bookings") / 100.0 * 0.2)
                    +
                    # Preference match
                    (F("category_match") * 0.3),
                    output_field=FloatField(),
                ),
            )

            # Return new specialists ranked by discovery score
            return queryset.filter(
                category_match__gt=0
            ).order_by(  # Ensure some preference match
                "-discovery_score", "-avg_rating"
            )[
                :limit
            ]
        else:
            # No preference data, return top-rated new specialists
            return queryset.order_by("-avg_rating", "-total_bookings")[:limit]
