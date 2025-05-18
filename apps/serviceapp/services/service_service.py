from django.db import transaction
from django.db.models import Q

from apps.categoriesapp.models import Category
from apps.serviceapp.models import (
    Service,
    ServiceAftercare,
    ServiceAvailability,
    ServiceException,
    ServiceFAQ,
    ServiceOverview,
    ServiceStep,
)
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist, SpecialistService


class ServiceService:
    """
    Service for managing services and their related objects
    """

    @staticmethod
    @transaction.atomic
    def create_service(service_data, availability_data=None, specialist_ids=None):
        """
        Create a new service with availability and specialists

        Parameters:
        - service_data: Dictionary with Service model fields
        - availability_data: Optional list of ServiceAvailability data
        - specialist_ids: Optional list of specialist IDs to assign

        Returns the created Service object
        """
        # Validate shop and category exist
        shop_id = service_data.get("shop_id")
        category_id = service_data.get("category_id")

        shop = Shop.objects.get(id=shop_id)
        category = Category.objects.get(id=category_id)

        # Create service
        service = Service.objects.create(
            shop=shop,
            category=category,
            name=service_data.get("name"),
            description=service_data.get("description", ""),
            short_description=service_data.get("short_description", ""),
            image=service_data.get("image"),
            price=service_data.get("price"),
            duration=service_data.get("duration"),
            slot_granularity=service_data.get("slot_granularity", 30),
            buffer_before=service_data.get("buffer_before", 0),
            buffer_after=service_data.get("buffer_after", 0),
            service_location=service_data.get("service_location"),
            has_custom_availability=service_data.get("has_custom_availability", False),
            min_booking_notice=service_data.get("min_booking_notice", 0),
            max_advance_booking_days=service_data.get("max_advance_booking_days", 30),
            order=service_data.get("order", 0),
            is_featured=service_data.get("is_featured", False),
            status=service_data.get("status", "active"),
        )

        # Create availability if provided
        if availability_data:
            for availability in availability_data:
                ServiceAvailability.objects.create(
                    service=service,
                    weekday=availability.get("weekday"),
                    from_hour=availability.get("from_hour"),
                    to_hour=availability.get("to_hour"),
                    is_closed=availability.get("is_closed", False),
                )

        # Assign specialists if provided
        if specialist_ids:
            for specialist_id in specialist_ids:
                specialist = Specialist.objects.get(id=specialist_id)

                # Ensure specialist belongs to the same shop
                if specialist.employee.shop_id == shop.id:
                    SpecialistService.objects.create(specialist=specialist, service=service)

        return service

    @staticmethod
    @transaction.atomic
    def update_service(service_id, service_data):
        """
        Update a service

        Parameters:
        - service_id: ID of service to update
        - service_data: Dictionary with Service model fields to update

        Returns the updated Service object
        """
        service = Service.objects.get(id=service_id)

        # Update category if provided
        if "category_id" in service_data:
            category = Category.objects.get(id=service_data["category_id"])
            service.category = category

        # Update other fields
        update_fields = [
            "name",
            "description",
            "short_description",
            "image",
            "price",
            "duration",
            "slot_granularity",
            "buffer_before",
            "buffer_after",
            "service_location",
            "has_custom_availability",
            "min_booking_notice",
            "max_advance_booking_days",
            "order",
            "is_featured",
            "status",
        ]

        for field in update_fields:
            if field in service_data:
                setattr(service, field, service_data[field])

        service.save()
        return service

    @staticmethod
    @transaction.atomic
    def update_service_availability(service_id, availability_data):
        """
        Update service availability

        Parameters:
        - service_id: ID of service to update
        - availability_data: List of availability objects with weekday, from_hour, to_hour, is_closed

        Returns the service object
        """
        service = Service.objects.get(id=service_id)

        # Delete existing availability
        ServiceAvailability.objects.filter(service=service).delete()

        # Create new availability
        for availability in availability_data:
            ServiceAvailability.objects.create(
                service=service,
                weekday=availability.get("weekday"),
                from_hour=availability.get("from_hour"),
                to_hour=availability.get("to_hour"),
                is_closed=availability.get("is_closed", False),
            )

        # Set has_custom_availability flag
        service.has_custom_availability = True
        service.save()

        return service

    @staticmethod
    @transaction.atomic
    def update_service_status(service_id, status):
        """Update service status (active, inactive, draft, archived)"""
        service = Service.objects.get(id=service_id)
        service.status = status
        service.save()
        return service

    @staticmethod
    @transaction.atomic
    def manage_specialists(service_id, specialist_ids, replace=False):
        """
        Add or remove specialists for a service

        Parameters:
        - service_id: ID of service to update
        - specialist_ids: List of specialist IDs to assign
        - replace: If True, replace all existing specialists with the new list
                  If False, add the new specialists to existing ones

        Returns the service object
        """
        service = Service.objects.get(id=service_id)

        # If replacing, delete all existing assignments
        if replace:
            SpecialistService.objects.filter(service=service).delete()

        # Get existing specialist IDs to avoid duplicates
        existing_ids = SpecialistService.objects.filter(service=service).values_list(
            "specialist_id", flat=True
        )

        # Add new specialists
        for specialist_id in specialist_ids:
            if specialist_id in existing_ids and not replace:
                continue  # Skip existing if not replacing

            try:
                specialist = Specialist.objects.get(id=specialist_id)

                # Ensure specialist belongs to the same shop
                if specialist.employee.shop_id == service.shop_id:
                    SpecialistService.objects.create(specialist=specialist, service=service)
            except Specialist.DoesNotExist:
                continue  # Skip invalid specialist

        return service

    @staticmethod
    @transaction.atomic
    def remove_specialist(service_id, specialist_id):
        """Remove a specialist from a service"""
        service = Service.objects.get(id=service_id)
        specialist = Specialist.objects.get(id=specialist_id)

        SpecialistService.objects.filter(service=service, specialist=specialist).delete()

        return service

    @staticmethod
    @transaction.atomic
    def add_service_exception(service_id, date, is_closed, from_hour=None, to_hour=None, reason=""):
        """
        Add a service exception (special day or holiday)

        Parameters:
        - service_id: ID of service
        - date: Date of exception
        - is_closed: Whether service is closed on this date
        - from_hour: Alternative opening hour (if not closed)
        - to_hour: Alternative closing hour (if not closed)
        - reason: Reason for exception

        Returns the created ServiceException object
        """
        service = Service.objects.get(id=service_id)

        # Check if exception already exists for this date
        exception, created = ServiceException.objects.get_or_create(
            service=service,
            date=date,
            defaults={
                "is_closed": is_closed,
                "from_hour": from_hour,
                "to_hour": to_hour,
                "reason": reason,
            },
        )

        if not created:
            # Update existing exception
            exception.is_closed = is_closed
            exception.from_hour = from_hour
            exception.to_hour = to_hour
            exception.reason = reason
            exception.save()

        return exception

    @staticmethod
    def remove_service_exception(service_id, date):
        """Remove a service exception for a specific date"""
        service = Service.objects.get(id=service_id)

        ServiceException.objects.filter(service=service, date=date).delete()

        return True

    @staticmethod
    @transaction.atomic
    def duplicate_service(service_id, new_name=None, include_specialists=True):
        """
        Duplicate a service with all its associated data

        Parameters:
        - service_id: ID of service to duplicate
        - new_name: Optional new name for the duplicate
        - include_specialists: Whether to duplicate specialist assignments

        Returns the newly created Service object
        """
        service = Service.objects.get(id=service_id)

        # Create a copy of the service
        service.pk = None  # Clear primary key to create a new instance

        if new_name:
            service.name = new_name
        else:
            service.name = f"{service.name} (Copy)"

        service.save()  # Save the new service

        # Duplicate availability
        availability_records = ServiceAvailability.objects.filter(service_id=service_id)
        for availability in availability_records:
            availability.pk = None  # Clear primary key
            availability.service = service
            availability.save()

        # Duplicate FAQs
        faqs = ServiceFAQ.objects.filter(service_id=service_id)
        for faq in faqs:
            faq.pk = None
            faq.service = service
            faq.save()

        # Duplicate overviews
        overviews = ServiceOverview.objects.filter(service_id=service_id)
        for overview in overviews:
            overview.pk = None
            overview.service = service
            overview.save()

        # Duplicate steps
        steps = ServiceStep.objects.filter(service_id=service_id)
        for step in steps:
            step.pk = None
            step.service = service
            step.save()

        # Duplicate aftercare tips
        aftercare_tips = ServiceAftercare.objects.filter(service_id=service_id)
        for tip in aftercare_tips:
            tip.pk = None
            tip.service = service
            tip.save()

        # Duplicate specialist assignments if requested
        if include_specialists:
            specialist_services = SpecialistService.objects.filter(service_id=service_id)
            for specialist_service in specialist_services:
                specialist_service.pk = None
                specialist_service.service = service
                specialist_service.save()

        return service

    @staticmethod
    def search_services(
        query, shop_id=None, category_id=None, service_location=None, status="active"
    ):
        """
        Search for services with advanced filtering

        Parameters:
        - query: Search term for name, description
        - shop_id: Optional filter by shop
        - category_id: Optional filter by category
        - service_location: Optional filter by location type
        - status: Filter by status (default active)

        Returns a queryset of matching Services
        """
        services = Service.objects.all()

        # Filter by shop if provided
        if shop_id:
            services = services.filter(shop_id=shop_id)

        # Filter by category if provided
        if category_id:
            # Include subcategories
            from apps.categoriesapp.models import Category

            categories = Category.objects.filter(Q(id=category_id) | Q(parent_id=category_id))
            services = services.filter(category__in=categories)

        # Filter by service location if provided
        if service_location:
            services = services.filter(service_location=service_location)

        # Filter by status
        if status:
            services = services.filter(status=status)

        # Filter by search query if provided
        if query:
            services = services.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(short_description__icontains=query)
            )

        return services.order_by("order", "name")

    @staticmethod
    def get_top_services(shop_id=None, limit=10):
        """
        Get top services by booking count and ratings

        Parameters:
        - shop_id: Optional filter by shop
        - limit: Number of services to return

        Returns list of top service objects with stats
        """
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Avg, Count

        from apps.bookingapp.models import Appointment

        # Start with active services
        services = Service.objects.filter(status="active")

        # Filter by shop if provided
        if shop_id:
            services = services.filter(shop_id=shop_id)

        # Get booking counts
        service_content_type = ContentType.objects.get_for_model(Service)

        booking_counts = (
            Appointment.objects.filter(service__in=services, status="completed")
            .values("service_id")
            .annotate(booking_count=Count("id"))
        )

        # Convert to dictionary for easier lookup
        booking_dict = {item["service_id"]: item["booking_count"] for item in booking_counts}

        # Get ratings
        from apps.reviewapp.models import Review

        ratings = (
            Review.objects.filter(
                content_type=service_content_type,
                object_id__in=services.values_list("id", flat=True),
            )
            .values("object_id")
            .annotate(avg_rating=Avg("rating"), rating_count=Count("id"))
        )

        # Convert to dictionary for easier lookup
        rating_dict = {
            str(item["object_id"]): {
                "avg_rating": item["avg_rating"],
                "rating_count": item["rating_count"],
            }
            for item in ratings
        }

        # Calculate a combined score for each service
        scored_services = []

        for service in services:
            service_id_str = str(service.id)

            # Get booking count (default 0)
            booking_count = booking_dict.get(service.id, 0)

            # Get rating data (default 0)
            rating_data = rating_dict.get(service_id_str, {"avg_rating": 0, "rating_count": 0})
            avg_rating = rating_data["avg_rating"] or 0
            rating_count = rating_data["rating_count"]

            # Calculate score
            # Weighted formula: 0.5 * normalized_booking_count + 0.5 * avg_rating
            # Max booking count used for normalization
            max_booking_count = max(booking_dict.values()) if booking_dict else 1
            normalized_bookings = (booking_count / max_booking_count) * 5  # Scale to 0-5

            # Apply minimum thresholds to avoid random services with few bookings/ratings
            if booking_count < 3 and rating_count < 3:
                continue

            # Apply simple bayesian average for ratings to handle few ratings
            # Formula: (avg_rating * rating_count + default * weight) / (rating_count + weight)
            default_rating = 3.0  # Average rating
            weight = 5  # Weight of the default rating
            bayesian_rating = (avg_rating * rating_count + default_rating * weight) / (
                rating_count + weight
            )

            # Calculate final score
            score = (0.5 * normalized_bookings) + (0.5 * bayesian_rating)

            scored_services.append(
                {
                    "service": service,
                    "booking_count": booking_count,
                    "avg_rating": avg_rating,
                    "rating_count": rating_count,
                    "score": score,
                }
            )

        # Sort by score (descending) and take top limit
        scored_services.sort(key=lambda x: x["score"], reverse=True)

        # Return top services with stats
        top_services = []
        for item in scored_services[:limit]:
            service = item["service"]
            top_services.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "shop_id": service.shop_id,
                    "shop_name": service.shop.name,
                    "image": service.image.url if service.image else None,
                    "price": service.price,
                    "duration": service.duration,
                    "booking_count": item["booking_count"],
                    "avg_rating": item["avg_rating"],
                    "rating_count": item["rating_count"],
                    "score": item["score"],
                }
            )

        return top_services
