from django.db import transaction
from django.db.models import Count

from apps.customersapp.models import CustomerCategory


class PreferenceExtractor:
    """
    Sophisticated algorithm to extract customer preferences from their behavior
    """

    @staticmethod
    @transaction.atomic
    def update_from_appointment(appointment):
        """
        Update customer preferences based on appointment data
        """
        # Get customer profile
        try:
            customer = appointment.customer.customer_profile
        except Exception:
            # Customer profile doesn't exist
            return

        # Extract category from service
        category = appointment.service.category

        # Update category affinity
        PreferenceExtractor._update_category_affinity(customer, category)

        # If it's a new/first-time booking with this category,
        # try to find related categories
        PreferenceExtractor._find_related_categories(customer, category)

    @staticmethod
    @transaction.atomic
    def update_from_content_interaction(
        customer, content_type, content_id, interaction_type
    ):
        """
        Update customer preferences based on content interactions (views, likes, etc.)

        content_type: 'reel', 'story', 'service'
        interaction_type: 'view', 'like', 'share', 'favorite'
        """
        # Different weights based on interaction type
        weights = {"view": 0.1, "like": 0.3, "share": 0.5, "favorite": 0.8}

        weight = weights.get(interaction_type, 0.1)

        # Get category from content
        category = None

        if content_type == "reel":
            from apps.reelsapp.models import Reel

            try:
                reel = Reel.objects.get(id=content_id)

                # If reel is linked to a service, use service category
                if hasattr(reel, "service") and reel.service:
                    category = reel.service.category
                # Otherwise use shop's primary category
                elif hasattr(reel, "shop") and reel.shop:
                    # Get most common category in shop services
                    from apps.serviceapp.models import Service

                    service_categories = (
                        Service.objects.filter(shop=reel.shop)
                        .values("category")
                        .annotate(count=Count("id"))
                        .order_by("-count")
                    )

                    if service_categories.exists():
                        from apps.categoriesapp.models import Category

                        category_id = service_categories[0]["category"]
                        category = Category.objects.get(id=category_id)
            except Exception:
                pass

        elif content_type == "service":
            from apps.serviceapp.models import Service

            try:
                service = Service.objects.get(id=content_id)
                category = service.category
            except Exception:
                pass

        # Update category affinity if found
        if category:
            PreferenceExtractor._update_category_affinity(customer, category, weight)

    @staticmethod
    def _update_category_affinity(customer, category, weight=0.5):
        """
        Update the affinity score for a category

        Uses a sophisticated decay model - older interactions have diminishing weight
        """
        # Get or create the category interest
        category_interest, created = CustomerCategory.objects.get_or_create(
            customer=customer, category=category, defaults={"affinity_score": weight}
        )

        if not created:
            # Decay existing score (70% of old score + new interaction)
            # This ensures newer interactions have more impact while preserving history
            new_score = (category_interest.affinity_score * 0.7) + weight

            # Cap at 1.0
            category_interest.affinity_score = min(new_score, 1.0)
            category_interest.save()

        # Also update parent category with lower weight
        if category.parent:
            parent_category = category.parent
            PreferenceExtractor._update_category_affinity(
                customer, parent_category, weight * 0.3
            )

    @staticmethod
    def _find_related_categories(customer, category):
        """
        Find related categories that the customer might be interested in
        """

        from apps.bookingapp.models import Appointment
        from apps.categoriesapp.models import Category

        # Find what other categories are commonly booked by customers who booked this category
        common_categories = (
            Appointment.objects.filter(service__category=category)
            .exclude(customer=customer.user)
            .values("service__category")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

        # Get category IDs from query
        category_ids = [item["service__category"] for item in common_categories]

        # Get categories and add with lower affinity scores
        related_categories = Category.objects.filter(id__in=category_ids)

        for related in related_categories:
            # Skip if same as original
            if related.id == category.id:
                continue

            # Add with low affinity score
            CustomerCategory.objects.get_or_create(
                customer=customer, category=related, defaults={"affinity_score": 0.1}
            )

    @staticmethod
    def extract_time_preferences(customer):
        """
        Analyze booking patterns to extract time-of-day and day-of-week preferences
        """
        from django.db.models.functions import ExtractHour, ExtractWeekDay

        from apps.bookingapp.models import Appointment

        # Get customer's appointments
        appointments = Appointment.objects.filter(
            customer=customer.user, status__in=["completed", "confirmed", "scheduled"]
        )

        # Not enough data to extract preferences
        if appointments.count() < 3:
            return {"time_of_day": {}, "day_of_week": {}}

        # Extract hour of day preferences
        hour_distribution = (
            appointments.annotate(hour=ExtractHour("start_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Extract day of week preferences
        day_distribution = (
            appointments.annotate(day=ExtractWeekDay("start_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Convert to normalized scores
        total_bookings = appointments.count()

        time_of_day = {}
        for item in hour_distribution:
            hour = item["hour"]
            count = item["count"]
            score = count / total_bookings
            time_of_day[hour] = score

        day_of_week = {}
        for item in day_distribution:
            day = item["day"]
            count = item["count"]
            score = count / total_bookings
            day_of_week[day] = score

        return {"time_of_day": time_of_day, "day_of_week": day_of_week}
