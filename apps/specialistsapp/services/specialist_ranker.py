from django.db.models import Case, Count, ExpressionWrapper, F, FloatField, Max, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from apps.specialistsapp.constants import (
    BOOKING_COUNT_WEIGHT,
    EXPERIENCE_WEIGHT,
    PORTFOLIO_WEIGHT,
    RATING_WEIGHT,
    VERIFICATION_WEIGHT,
)
from apps.specialistsapp.models import Specialist


class SpecialistRanker:
    """
    Service for ranking and sorting specialists based on multiple criteria
    using sophisticated weighting algorithms.
    """

    def get_top_rated_specialists(self, queryset=None, limit=10):
        """
        Get top rated specialists based on a composite score of ratings,
        booking count, experience, and other factors.

        Args:
            queryset: Optional QuerySet to filter specialists (defaults to all active)
            limit: Maximum number of specialists to return

        Returns:
            QuerySet of top specialists with calculated scores
        """
        # Start with all active specialists if no queryset provided
        if queryset is None:
            queryset = Specialist.objects.filter(
                employee__is_active=True, employee__shop__is_active=True
            )

        # Select related/prefetch common relationships
        queryset = queryset.select_related(
            "employee", "employee__shop", "employee__user"
        ).prefetch_related("specialist_services", "specialist_services__service", "expertise")

        # Add normalized score components
        max_booking_count = (
            queryset.aggregate(max_count=Coalesce(Max("total_bookings"), Value(1)))["max_count"]
            or 1
        )
        max_experience = (
            queryset.aggregate(max_exp=Coalesce(Max("experience_years"), Value(1)))["max_exp"] or 1
        )

        # Start by annotating score components
        queryset = queryset.annotate(
            # 1. Rating component (already normalized 0-5)
            rating_component=ExpressionWrapper(
                Coalesce(F("avg_rating"), 0) / 5.0 * RATING_WEIGHT,
                output_field=FloatField(),
            ),
            # 2. Booking count component (normalized)
            booking_component=ExpressionWrapper(
                Coalesce(F("total_bookings"), 0) / float(max_booking_count) * BOOKING_COUNT_WEIGHT,
                output_field=FloatField(),
            ),
            # 3. Experience component (normalized)
            experience_component=ExpressionWrapper(
                Coalesce(F("experience_years"), 0) / float(max_experience) * EXPERIENCE_WEIGHT,
                output_field=FloatField(),
            ),
            # 4. Portfolio component (based on count & featured)
            portfolio_count=Count("portfolio"),
            # 5. Verification bonus
            verification_component=Case(
                When(is_verified=True, then=VERIFICATION_WEIGHT),
                default=Value(0),
                output_field=FloatField(),
            ),
        )

        # Calculate portfolio component
        max_portfolio = (
            queryset.aggregate(max_port=Coalesce(Max("portfolio_count"), Value(1)))["max_port"] or 1
        )

        queryset = queryset.annotate(
            portfolio_component=ExpressionWrapper(
                F("portfolio_count") / float(max_portfolio) * PORTFOLIO_WEIGHT,
                output_field=FloatField(),
            ),
            # Combine all components for final score
            total_score=ExpressionWrapper(
                F("rating_component")
                + F("booking_component")
                + F("experience_component")
                + F("portfolio_component")
                + F("verification_component"),
                output_field=FloatField(),
            ),
        )

        # Order by total score and return limited results
        return queryset.order_by("-total_score", "-avg_rating", "-total_bookings")[:limit]

    def rank_specialists_for_service(self, service_id, limit=5):
        """
        Rank specialists specifically for a service, considering service-specific
        metrics like proficiency and booking history for that service.

        Args:
            service_id: UUID of the service
            limit: Maximum number of specialists to return

        Returns:
            QuerySet of ranked specialists for the service
        """
        from apps.serviceapp.models import Service

        # Get service and ensure it exists
        service = Service.objects.get(id=service_id)

        # Get specialists who provide this service
        specialists = Specialist.objects.filter(
            specialist_services__service=service,
            employee__is_active=True,
            employee__shop__is_active=True,
        ).select_related("employee", "employee__shop")

        # Enhanced ranking criteria for service-specific ranking
        specialists = specialists.annotate(
            # Service-specific booking count
            service_bookings=Count(
                "appointments",
                filter=Q(appointments__service=service, appointments__status="completed"),
            ),
            # Service proficiency level from specialist_service relation
            proficiency=Coalesce(
                F("specialist_services__proficiency_level"),
                Value(3),  # Default if not specified
                output_field=FloatField(),
            ),
            # Recent service success (completions in last 30 days)
            recent_completions=Count(
                "appointments",
                filter=Q(
                    appointments__service=service,
                    appointments__status="completed",
                    appointments__end_time__gte=timezone.now() - timezone.timedelta(days=30),
                ),
            ),
            # No-show rate for this service (negative impact)
            no_show_count=Count(
                "appointments",
                filter=Q(appointments__service=service, appointments__status="no_show"),
            ),
        )

        # Calculate normalized scores for service-specific ranking
        max_service_bookings = (
            specialists.aggregate(max_count=Coalesce(Max("service_bookings"), Value(1)))[
                "max_count"
            ]
            or 1
        )
        max_recent = (
            specialists.aggregate(max_recent=Coalesce(Max("recent_completions"), Value(1)))[
                "max_recent"
            ]
            or 1
        )

        specialists = specialists.annotate(
            # 1. General quality score (from overall ranking)
            general_score=ExpressionWrapper(
                (Coalesce(F("avg_rating"), 0) / 5.0 * 0.3)
                + (
                    Case(
                        When(is_verified=True, then=0.1),
                        default=Value(0),
                        output_field=FloatField(),
                    )
                ),
                output_field=FloatField(),
            ),
            # 2. Service expertise score
            expertise_score=ExpressionWrapper(
                (F("proficiency") / 5.0 * 0.25)
                + (F("service_bookings") / float(max_service_bookings) * 0.2),
                output_field=FloatField(),
            ),
            # 3. Recent success score
            recency_score=ExpressionWrapper(
                F("recent_completions") / float(max_recent) * 0.15,
                output_field=FloatField(),
            ),
            # 4. Reliability score (negative impact of no-shows)
            reliability_score=ExpressionWrapper(
                Case(
                    When(service_bookings=0, then=0.1),  # Default if no bookings
                    default=Value(0.1) * (Value(1) - F("no_show_count") / F("service_bookings")),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            ),
            # Combine for service-specific score
            service_score=ExpressionWrapper(
                F("general_score")
                + F("expertise_score")
                + F("recency_score")
                + F("reliability_score"),
                output_field=FloatField(),
            ),
        )

        # Return specialists ranked for this specific service
        return specialists.order_by("-service_score", "-avg_rating", "-service_bookings")[:limit]

    def get_similar_specialists(self, specialist_id, limit=5):
        """
        Find specialists similar to a given specialist based on services,
        expertise categories and other attributes.

        Args:
            specialist_id: UUID of the reference specialist
            limit: Maximum number of similar specialists to return

        Returns:
            QuerySet of similar specialists
        """
        # Get reference specialist
        reference = Specialist.objects.get(id=specialist_id)

        # Get the shop to exclude the reference specialist from results
        shop = reference.employee.shop

        # Get reference specialist's services and categories
        service_ids = reference.specialist_services.values_list("service_id", flat=True)
        category_ids = reference.expertise.values_list("id", flat=True)

        # Find specialists with similar services or expertise
        similar_specialists = (
            Specialist.objects.filter(
                # Must be active and from the same shop
                employee__is_active=True,
                employee__shop=shop,
            )
            .exclude(
                # Exclude the reference specialist
                id=specialist_id
            )
            .annotate(
                # Count matching services
                matching_services=Count(
                    "specialist_services",
                    filter=Q(specialist_services__service_id__in=service_ids),
                ),
                # Count matching categories
                matching_categories=Count("expertise", filter=Q(expertise__id__in=category_ids)),
            )
            .annotate(
                # Calculate similarity score
                similarity_score=ExpressionWrapper(
                    (F("matching_services") * 0.6) + (F("matching_categories") * 0.4),
                    output_field=FloatField(),
                )
            )
        )

        # Return most similar specialists
        return similar_specialists.order_by("-similarity_score", "-avg_rating")[:limit]

    def get_specialists_by_category(self, category_id, limit=10):
        """
        Get top specialists in a specific category.

        Args:
            category_id: UUID of the category
            limit: Maximum number of specialists to return

        Returns:
            QuerySet of top specialists in the category
        """
        # Get specialists in this category (both via expertise and services)
        specialists = Specialist.objects.filter(
            Q(expertise__id=category_id) | Q(specialist_services__service__category_id=category_id),
            employee__is_active=True,
            employee__shop__is_active=True,
        ).distinct()

        # Apply standard ranking algorithm to this filtered set
        return self.get_top_rated_specialists(specialists, limit)

    def get_trending_specialists(self, days=30, limit=10):
        """
        Get trending specialists based on recent booking growth and engagement.

        Args:
            days: Timeframe for trend analysis
            limit: Maximum number of specialists to return

        Returns:
            QuerySet of trending specialists
        """

        # Calculate date ranges
        now = timezone.now()
        recent_start = now - timezone.timedelta(days=days)
        previous_start = recent_start - timezone.timedelta(days=days)

        # Get all active specialists
        specialists = Specialist.objects.filter(
            employee__is_active=True, employee__shop__is_active=True
        )

        # Annotate with recent and previous period metrics
        specialists = specialists.annotate(
            # Recent period bookings
            recent_bookings=Count(
                "appointments",
                filter=Q(
                    appointments__created_at__gte=recent_start,
                    appointments__created_at__lt=now,
                ),
            ),
            # Previous period bookings
            previous_bookings=Count(
                "appointments",
                filter=Q(
                    appointments__created_at__gte=previous_start,
                    appointments__created_at__lt=recent_start,
                ),
            ),
            # Recent portfolio engagement (likes)
            recent_portfolio_likes=Sum(
                "portfolio__likes_count",
                filter=Q(portfolio__created_at__gte=recent_start),
            ),
        )

        # Calculate growth and trend score
        specialists = specialists.annotate(
            # Booking growth rate (avoid division by zero)
            booking_growth=Case(
                When(previous_bookings=0, then=F("recent_bookings")),
                default=ExpressionWrapper(
                    (F("recent_bookings") - F("previous_bookings"))
                    / Cast(F("previous_bookings"), FloatField()),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            ),
            # Combine for trend score (weighted)
            trend_score=ExpressionWrapper(
                (F("booking_growth") * 0.7) + (Coalesce(F("recent_portfolio_likes"), 0) * 0.3),
                output_field=FloatField(),
            ),
        )

        # Get specialists with positive trend score and order by highest score
        return specialists.filter(trend_score__gt=0).order_by(
            "-trend_score", "-recent_bookings", "-avg_rating"
        )[:limit]
