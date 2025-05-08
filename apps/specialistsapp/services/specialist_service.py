from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.specialistsapp.constants import (
    SPECIALIST_CACHE_KEY,
    SPECIALIST_SERVICES_CACHE_KEY,
)
from apps.specialistsapp.models import (
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class SpecialistService:
    """Service for managing specialists"""

    @transaction.atomic
    def create_specialist(self, employee, data):
        """
        Create a new specialist profile for an employee.

        Args:
            employee: Employee object
            data: Dictionary containing specialist data

        Returns:
            Created Specialist object
        """
        # Check if employee already has a specialist profile
        if hasattr(employee, "specialist"):
            raise ValidationError(_("Employee already has a specialist profile."))

        # Create specialist
        specialist = Specialist.objects.create(
            employee=employee,
            bio=data.get("bio", ""),
            experience_years=data.get("experience_years", 0),
            experience_level=data.get("experience_level", "intermediate"),
        )

        # Add expertise categories if provided
        if "expertise_ids" in data and data["expertise_ids"]:
            from apps.categoriesapp.models import Category

            categories = Category.objects.filter(id__in=data["expertise_ids"])
            specialist.expertise.set(categories)

        # Add services if provided
        if "service_ids" in data and data["service_ids"]:
            from apps.serviceapp.models import Service

            shop = employee.shop
            services = Service.objects.filter(id__in=data["service_ids"], shop=shop)

            for i, service in enumerate(services):
                SpecialistService.objects.create(
                    specialist=specialist,
                    service=service,
                    is_primary=(i == 0),  # First service is primary
                )

        # Create working hours if provided
        if "working_hours" in data and data["working_hours"]:
            for hours_data in data["working_hours"]:
                SpecialistWorkingHours.objects.create(
                    specialist=specialist,
                    weekday=hours_data.get("weekday"),
                    from_hour=hours_data.get("from_hour"),
                    to_hour=hours_data.get("to_hour"),
                    is_off=hours_data.get("is_off", False),
                )
        else:
            # Create default working hours (9AM-5PM, Sun-Thu, Friday off)
            from apps.specialistsapp.constants import (
                DEFAULT_END_HOUR,
                DEFAULT_START_HOUR,
            )

            for day in range(7):  # 0=Sunday, 6=Saturday
                SpecialistWorkingHours.objects.create(
                    specialist=specialist,
                    weekday=day,
                    from_hour=DEFAULT_START_HOUR,
                    to_hour=DEFAULT_END_HOUR,
                    is_off=(day == 5),  # Friday off by default
                )

        # If shop is verified, auto-verify specialist
        shop = employee.shop
        if shop.is_verified:
            specialist.is_verified = True
            specialist.verified_at = timezone.now()
            specialist.save()

        return specialist

    @transaction.atomic
    def update_specialist(self, specialist, data):
        """
        Update a specialist profile.

        Args:
            specialist: Specialist object
            data: Dictionary containing updated data

        Returns:
            Updated Specialist object
        """
        # Update basic fields
        if "bio" in data:
            specialist.bio = data["bio"]

        if "experience_years" in data:
            specialist.experience_years = data["experience_years"]

        if "experience_level" in data:
            specialist.experience_level = data["experience_level"]

        specialist.save()

        # Update expertise categories if provided
        if "expertise_ids" in data:
            from apps.categoriesapp.models import Category

            categories = Category.objects.filter(id__in=data["expertise_ids"])
            specialist.expertise.set(categories)

        # Clear cache
        cache.delete(SPECIALIST_CACHE_KEY.format(id=specialist.id))

        return specialist

    @transaction.atomic
    def verify_specialist(self, specialist, verified_by=None):
        """
        Verify a specialist profile.

        Args:
            specialist: Specialist object
            verified_by: Optional User who verified the specialist

        Returns:
            Updated Specialist object
        """
        specialist.is_verified = True
        specialist.verified_at = timezone.now()
        specialist.save()

        # Send notification to specialist's user
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        NotificationService.send_notification(
            user_id=specialist.employee.user.id,
            notification_type="specialist_verified",
            data={
                "specialist_id": str(specialist.id),
                "specialist_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                "shop_name": specialist.employee.shop.name,
            },
        )

        # Clear cache
        cache.delete(SPECIALIST_CACHE_KEY.format(id=specialist.id))

        return specialist

    @transaction.atomic
    def add_service(self, specialist, service, data=None):
        """
        Add a service to a specialist.

        Args:
            specialist: Specialist object
            service: Service object
            data: Optional dictionary with additional data

        Returns:
            Created SpecialistService object
        """
        # Check if service is already assigned
        if SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists():
            raise ValidationError(_("Service is already assigned to this specialist."))

        # Check if service belongs to the shop
        if service.shop_id != specialist.employee.shop_id:
            raise ValidationError(
                _("Service does not belong to the specialist's shop.")
            )

        # Create specialist service
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=service,
            is_primary=data.get("is_primary", False) if data else False,
            proficiency_level=data.get("proficiency_level", 3) if data else 3,
            custom_duration=data.get("custom_duration") if data else None,
        )

        # If marked as primary, update other services
        if specialist_service.is_primary:
            SpecialistService.objects.filter(
                specialist=specialist, is_primary=True
            ).exclude(id=specialist_service.id).update(is_primary=False)

        # Clear cache
        cache.delete(SPECIALIST_SERVICES_CACHE_KEY.format(id=specialist.id))

        return specialist_service

    @transaction.atomic
    def update_service(self, specialist_service, data):
        """
        Update a specialist service.

        Args:
            specialist_service: SpecialistService object
            data: Dictionary with updated data

        Returns:
            Updated SpecialistService object
        """
        # Update fields
        if "is_primary" in data:
            specialist_service.is_primary = data["is_primary"]

        if "proficiency_level" in data:
            specialist_service.proficiency_level = data["proficiency_level"]

        if "custom_duration" in data:
            specialist_service.custom_duration = data["custom_duration"]

        specialist_service.save()

        # If marked as primary, update other services
        if specialist_service.is_primary:
            SpecialistService.objects.filter(
                specialist=specialist_service.specialist, is_primary=True
            ).exclude(id=specialist_service.id).update(is_primary=False)

        # Clear cache
        cache.delete(
            SPECIALIST_SERVICES_CACHE_KEY.format(id=specialist_service.specialist_id)
        )

        return specialist_service

    def remove_service(self, specialist_service):
        """
        Remove a service from a specialist.

        Args:
            specialist_service: SpecialistService object

        Returns:
            Boolean indicating success
        """
        # Check if service has any bookings
        from apps.bookingapp.models import Appointment

        has_bookings = Appointment.objects.filter(
            specialist=specialist_service.specialist,
            service=specialist_service.service,
            status__in=["scheduled", "confirmed", "in_progress"],
        ).exists()

        if has_bookings:
            raise ValidationError(_("Cannot remove service with active bookings."))

        # Check if this is the only service for the specialist
        is_only_service = (
            SpecialistService.objects.filter(
                specialist=specialist_service.specialist
            ).count()
            <= 1
        )

        if is_only_service:
            raise ValidationError(
                _("Cannot remove the only service from a specialist.")
            )

        # If this is the primary service, set another one as primary
        if specialist_service.is_primary:
            next_service = (
                SpecialistService.objects.filter(
                    specialist=specialist_service.specialist
                )
                .exclude(id=specialist_service.id)
                .first()
            )

            if next_service:
                next_service.is_primary = True
                next_service.save()

        # Remove the service
        specialist_service.delete()

        # Clear cache
        cache.delete(
            SPECIALIST_SERVICES_CACHE_KEY.format(id=specialist_service.specialist_id)
        )

        return True

    @transaction.atomic
    def update_working_hours(self, specialist, working_hours_data):
        """
        Update working hours for a specialist.

        Args:
            specialist: Specialist object
            working_hours_data: List of working hours data

        Returns:
            List of updated SpecialistWorkingHours objects
        """
        updated_hours = []

        for hours_data in working_hours_data:
            weekday = hours_data.get("weekday")

            # Get or create working hours for this day
            working_hours, created = SpecialistWorkingHours.objects.get_or_create(
                specialist=specialist,
                weekday=weekday,
                defaults={
                    "from_hour": hours_data.get("from_hour"),
                    "to_hour": hours_data.get("to_hour"),
                    "is_off": hours_data.get("is_off", False),
                },
            )

            if not created:
                # Update existing hours
                working_hours.from_hour = hours_data.get("from_hour")
                working_hours.to_hour = hours_data.get("to_hour")
                working_hours.is_off = hours_data.get("is_off", False)
                working_hours.save()

            updated_hours.append(working_hours)

        # Clear cache
        cache.delete(SPECIALIST_CACHE_KEY.format(id=specialist.id))

        return updated_hours

    def get_specialist_services(self, specialist):
        """
        Get services provided by a specialist.

        Args:
            specialist: Specialist object

        Returns:
            QuerySet of SpecialistService objects
        """
        # Try to get from cache
        cache_key = SPECIALIST_SERVICES_CACHE_KEY.format(id=specialist.id)
        cached_services = cache.get(cache_key)

        if cached_services is not None:
            return cached_services

        # Get services from database
        services = (
            SpecialistService.objects.filter(specialist=specialist)
            .select_related("service", "service__category")
            .order_by("-is_primary", "-booking_count")
        )

        # Cache for 1 hour
        cache.set(cache_key, services, 60 * 60)

        return services
