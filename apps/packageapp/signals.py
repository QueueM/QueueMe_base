from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.bookingapp.models import Appointment

from .models import Package, PackageService


@receiver(post_save, sender=PackageService)
def update_package_total_duration(sender, instance, created, **kwargs):
    """
    Update the total duration of a package when a service is added or modified.
    """
    package = instance.package
    total_mins = sum(ps.effective_duration for ps in package.services.all())

    if total_mins != package.total_duration:
        package.total_duration = total_mins
        package.save(update_fields=["total_duration"])


@receiver(post_delete, sender=PackageService)
def recalculate_package_on_service_delete(sender, instance, **kwargs):
    """
    Recalculate package duration when a service is removed.
    """
    # Check if the package still exists (not being deleted in cascade)
    try:
        package = Package.objects.get(id=instance.package_id)
        total_mins = sum(ps.effective_duration for ps in package.services.all())
        package.total_duration = total_mins
        package.save(update_fields=["total_duration"])
    except Package.DoesNotExist:
        pass


@receiver(pre_save, sender=Package)
def check_package_status(sender, instance, **kwargs):
    """
    Automatically update package status based on dates and purchase limits.
    """
    if instance.status not in ["inactive", "expired"]:
        today = timezone.now().date()

        # Check if package is expired
        if instance.end_date and instance.end_date < today:
            instance.status = "expired"

        # Check if package is upcoming
        elif instance.start_date and instance.start_date > today:
            instance.status = "upcoming"

        # Check if package has reached purchase limit
        elif (
            instance.max_purchases
            and instance.current_purchases >= instance.max_purchases
        ):
            instance.status = "inactive"

        # Otherwise, keep or set to active
        elif instance.status != "active":
            instance.status = "active"


@receiver(post_save, sender=Appointment)
def update_package_purchases_count(sender, instance, created, **kwargs):
    """
    Update the purchase count of a package when an appointment is created or updated.
    This signal handles the case when a package is booked and the status changes.
    """
    # Check if appointment belongs to a package
    # This requires adding a package field to the Appointment model
    # Assumption: There's a way to identify package bookings (e.g., package_id field)

    # Check if appointment has a package reference
    package_id = getattr(instance, "package_id", None)

    if package_id and instance.status in ["scheduled", "confirmed"]:
        try:
            package = Package.objects.get(id=package_id)

            # If it's a new confirmed booking
            if created or (
                not created
                and instance.tracker.has_changed("status")
                and instance.tracker.previous("status")
                not in ["scheduled", "confirmed"]
            ):
                package.current_purchases += 1
                package.save(update_fields=["current_purchases"])

                # Check if we've reached the limit and update status if needed
                if (
                    package.max_purchases
                    and package.current_purchases >= package.max_purchases
                ):
                    package.status = "inactive"
                    package.save(update_fields=["status"])

        except Package.DoesNotExist:
            pass

    # Handle cancellations - decrement purchase count if an appointment is cancelled
    elif package_id and instance.status == "cancelled" and not created:
        try:
            package = Package.objects.get(id=package_id)

            # If status changed from confirmed/scheduled to cancelled
            if instance.tracker.has_changed("status") and instance.tracker.previous(
                "status"
            ) in [
                "scheduled",
                "confirmed",
            ]:
                if package.current_purchases > 0:
                    package.current_purchases -= 1
                    # Update status if it was inactive due to reaching limit
                    if (
                        package.status == "inactive"
                        and package.max_purchases
                        and package.current_purchases < package.max_purchases
                    ):
                        package.status = "active"
                    package.save(update_fields=["current_purchases", "status"])

        except Package.DoesNotExist:
            pass
