from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.specialistsapp.models import SpecialistService

from .models import Service, ServiceAvailability


@receiver(pre_save, sender=Service)
def pre_save_service(sender, instance, **kwargs):
    """
    Handle price_halalas calculation before save
    This ensures the price_halalas field is correctly set
    """
    if instance.price is not None:
        instance.price_halalas = int(instance.price * 100)


@receiver(post_save, sender=Service)
def service_created(sender, instance, created, **kwargs):
    """
    Handle service creation
    - Create default availability if needed
    """
    if (
        created
        and instance.has_custom_availability
        and not ServiceAvailability.objects.filter(service=instance).exists()
    ):
        # Create default availability for all weekdays
        for weekday in range(7):
            # Default working hours (9 AM to 6 PM, closed on Friday)
            is_closed = weekday == 5  # Friday (5) is closed
            from_hour = "09:00:00"
            to_hour = "18:00:00"

            ServiceAvailability.objects.create(
                service=instance,
                weekday=weekday,
                from_hour=from_hour,
                to_hour=to_hour,
                is_closed=is_closed,
            )


@receiver(post_delete, sender=Service)
def service_deleted(sender, instance, **kwargs):
    """
    Handle service deletion
    - Clean up associated specialist services
    """
    # Delete related specialist services
    SpecialistService.objects.filter(service=instance).delete()


@receiver(post_save, sender=SpecialistService)
def specialist_service_created(sender, instance, created, **kwargs):
    """
    Handle creation of specialist service link
    - Ensure at least one specialist is assigned to the service
    """
    if created:
        # Update service specialists_count property (via annotation in queries)
        # This is just to make sure related service queries are refreshed
        instance.service.save(update_fields=["updated_at"])
