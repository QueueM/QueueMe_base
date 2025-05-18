from django.db.models import Avg, Count, F, Q

from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.specialistsapp.models import Specialist, SpecialistService


class ServiceMatcher:
    """
    Service for matching specialists to services based on various criteria

    This provides sophisticated algorithms for:
    1. Finding the best specialist for a service
    2. Suggesting services a specialist should add based on their skills
    3. Finding complementary services to suggest to customers
    """

    @staticmethod
    def find_optimal_specialist(service_id, time_slot=None, customer_id=None):
        """
        Find the optimal specialist for a service

        Parameters:
        - service_id: ID of the service to find specialists for
        - time_slot: Optional dict with date, start_time, end_time
        - customer_id: Optional customer ID to consider preferences

        Returns a ranked list of specialist IDs with scores
        """
        service = Service.objects.get(id=service_id)

        # Get all specialists who can perform this service
        specialists = Specialist.objects.filter(specialist_services__service=service)

        # If time_slot provided, filter for availability
        if time_slot:
            from apps.serviceapp.services.availability_service import AvailabilityService

            available_specialists = []
            for specialist in specialists:
                if AvailabilityService.is_specialist_available(
                    specialist,
                    time_slot["date"],
                    time_slot["start_time"],
                    time_slot["end_time"],
                    service.buffer_before,
                    service.buffer_after,
                ):
                    available_specialists.append(specialist.id)

            specialists = Specialist.objects.filter(id__in=available_specialists)

        # If no specialists available, return empty list
        if not specialists.exists():
            return []

        # Score specialists based on various factors
        scored_specialists = []

        for specialist in specialists:
            score = 0

            # Factor 1: Rating - Most significant factor (0-5 points)
            from django.contrib.contenttypes.models import ContentType

            specialist_content_type = ContentType.objects.get_for_model(Specialist)

            rating = (
                Review.objects.filter(
                    content_type=specialist_content_type, object_id=specialist.id
                ).aggregate(avg_rating=Avg("rating"))["avg_rating"]
                or 0
            )

            score += rating

            # Factor 2: Experience with this service (0-3 points)
            completed_appointments = specialist.appointments.filter(
                service=service, status="completed"
            ).count()

            if completed_appointments > 50:
                score += 3
            elif completed_appointments > 20:
                score += 2
            elif completed_appointments > 5:
                score += 1

            # Factor 3: Workload balance (0-2 points)
            # Prefer specialists with fewer upcoming appointments
            upcoming_appointments = specialist.appointments.filter(
                status__in=["scheduled", "confirmed"]
            ).count()

            if upcoming_appointments < 5:
                score += 2
            elif upcoming_appointments < 15:
                score += 1

            # Factor 4: Specialization - is this a primary service? (0-1 points)
            is_primary = SpecialistService.objects.filter(
                specialist=specialist, service=service, is_primary=True
            ).exists()

            if is_primary:
                score += 1

            # Factor 5: Customer preference (0-2 points)
            if customer_id:
                # Check if this customer has booked this specialist before
                previous_bookings = specialist.appointments.filter(
                    customer_id=customer_id, status="completed"
                ).count()

                if previous_bookings > 0:
                    score += 1

                # Check if customer has left positive review
                positive_review = Review.objects.filter(
                    content_type=specialist_content_type,
                    object_id=specialist.id,
                    user_id=customer_id,
                    rating__gte=4,
                ).exists()

                if positive_review:
                    score += 1

            # Add to results
            scored_specialists.append(
                {
                    "specialist_id": specialist.id,
                    "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                    "score": score,
                    "rating": rating,
                    "experience": completed_appointments,
                    "workload": upcoming_appointments,
                    "is_primary": is_primary,
                }
            )

        # Sort by score (descending)
        scored_specialists.sort(key=lambda x: x["score"], reverse=True)

        return scored_specialists

    @staticmethod
    def suggest_services_for_specialist(specialist_id):
        """
        Suggest services that a specialist could add based on skills, experience,
        and what other similar specialists offer

        Returns a list of recommended service IDs with reasons
        """
        specialist = Specialist.objects.get(id=specialist_id)

        # Get services this specialist already offers
        current_service_ids = SpecialistService.objects.filter(specialist=specialist).values_list(
            "service_id", flat=True
        )

        # Get services from the same shop
        shop_services = Service.objects.filter(shop=specialist.employee.shop).exclude(
            id__in=current_service_ids
        )

        # If no other services in shop, nothing to suggest
        if not shop_services.exists():
            return []

        suggestions = []

        # Strategy 1: Category-based suggestions
        # Find services in the same categories as services the specialist already offers
        specialist_categories = (
            Service.objects.filter(id__in=current_service_ids)
            .values_list("category_id", flat=True)
            .distinct()
        )

        category_matches = shop_services.filter(category_id__in=specialist_categories)

        for service in category_matches:
            suggestions.append(
                {
                    "service_id": service.id,
                    "name": service.name,
                    "reason": "Same category as your current services",
                    "score": 5,
                }
            )

        # Strategy 2: Find services commonly offered together with specialist's services
        # Look at other specialists who offer the same services
        similar_specialists = Specialist.objects.filter(
            specialist_services__service_id__in=current_service_ids
        ).exclude(id=specialist_id)

        for similar_specialist in similar_specialists:
            # Get services that this similar specialist offers but our specialist doesn't
            other_services = (
                SpecialistService.objects.filter(specialist=similar_specialist)
                .exclude(service_id__in=current_service_ids)
                .values_list("service_id", flat=True)
            )

            # Filter to services in our shop
            other_services_in_shop = shop_services.filter(id__in=other_services)

            for service in other_services_in_shop:
                # Check if already suggested
                existing = next((s for s in suggestions if s["service_id"] == service.id), None)

                if existing:
                    # Increase score for multiple recommendations
                    existing["score"] += 1
                    continue

                suggestions.append(
                    {
                        "service_id": service.id,
                        "name": service.name,
                        "reason": "Often provided together with your current services",
                        "score": 3,
                    }
                )

        # Strategy 3: Duration-based matching
        # Suggest services with similar duration to what specialist already provides
        specialist_durations = Service.objects.filter(id__in=current_service_ids).values_list(
            "duration", flat=True
        )

        # Calculate duration range (from min-10 to max+10 minutes)
        if specialist_durations:
            min_duration = max(0, min(specialist_durations) - 10)
            max_duration = max(specialist_durations) + 10

            duration_matches = shop_services.filter(
                duration__gte=min_duration, duration__lte=max_duration
            ).exclude(id__in=[s["service_id"] for s in suggestions])

            for service in duration_matches:
                suggestions.append(
                    {
                        "service_id": service.id,
                        "name": service.name,
                        "reason": "Similar duration to your current services",
                        "score": 1,
                    }
                )

        # Sort by score
        suggestions.sort(key=lambda x: x["score"], reverse=True)

        return suggestions

    @staticmethod
    def find_complementary_services(service_id, customer_id=None):
        """
        Find services that complement the given service

        This can be used to suggest additional services to customers
        """
        from apps.bookingapp.models import Appointment

        service = Service.objects.get(id=service_id)
        shop = service.shop

        # Get other active services in the same shop
        other_services = Service.objects.filter(shop=shop, status="active").exclude(id=service_id)

        complementary_services = []

        # Strategy 1: Category relationships
        # Services in the same category might be complementary
        same_category_services = other_services.filter(category=service.category)

        for complementary in same_category_services:
            complementary_services.append(
                {
                    "service_id": complementary.id,
                    "name": complementary.name,
                    "reason": "Similar service in the same category",
                    "score": 3,
                }
            )

        # Strategy 2: Booking patterns - Use Django ORM instead of raw SQL
        # Get customers who booked this service
        customers_with_service = (
            Appointment.objects.filter(service_id=service_id)
            .values_list("customer_id", flat=True)
            .distinct()
        )

        # Find other services booked by these customers in the same shop
        if customers_with_service:
            # Count frequency of each service
            service_frequencies = (
                Appointment.objects.filter(customer_id__in=customers_with_service, shop_id=shop.id)
                .exclude(service_id=service_id)
                .values("service_id")
                .annotate(frequency=Count("service_id"))
                .order_by("-frequency")[:5]
            )

            for freq_item in service_frequencies:
                complementary_id = freq_item["service_id"]
                frequency = freq_item["frequency"]

                # Get service details
                try:
                    complementary_service = Service.objects.get(id=complementary_id)

                    # Check if already in results
                    existing = next(
                        (s for s in complementary_services if s["service_id"] == complementary_id),
                        None,
                    )

                    if existing:
                        # Boost score
                        existing["score"] += min(5, frequency)  # Cap at +5 points
                        existing["reason"] = "Frequently booked together by other customers"
                    else:
                        complementary_services.append(
                            {
                                "service_id": complementary_id,
                                "name": complementary_service.name,
                                "reason": "Frequently booked together by other customers",
                                "score": min(5, frequency) + 1,  # Base score + frequency (capped)
                            }
                        )
                except Service.DoesNotExist:
                    # Skip if service no longer exists
                    continue

        # Strategy 3: If customer provided, use their history/preferences
        if customer_id:
            # Find services this customer has booked before
            customer_services = (
                Appointment.objects.filter(customer_id=customer_id, shop=shop)
                .exclude(service_id=service_id)
                .values_list("service_id", flat=True)
                .distinct()
            )

            previously_booked = other_services.filter(id__in=customer_services)

            for complementary in previously_booked:
                existing = next(
                    (s for s in complementary_services if s["service_id"] == complementary.id),
                    None,
                )

                if existing:
                    # If customer has booked before, it's a strong signal
                    existing["score"] += 4
                    existing["reason"] = "Service you've booked before"
                else:
                    complementary_services.append(
                        {
                            "service_id": complementary.id,
                            "name": complementary.name,
                            "reason": "Service you've booked before",
                            "score": 4,
                        }
                    )

        # Sort by score
        complementary_services.sort(key=lambda x: x["score"], reverse=True)

        return complementary_services[:5]  # Return top 5
