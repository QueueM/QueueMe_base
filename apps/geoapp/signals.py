from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Location


@receiver(pre_save, sender=Location)
def ensure_country_matches_city(sender, instance, **kwargs):
    """Ensure location's country matches its city's country"""
    if instance.city and instance.city.country:
        instance.country = instance.city.country


@receiver(post_save, sender=Location)
def update_city_center(sender, instance, created, **kwargs):
    """Update city center point if not set (average of all locations)"""
    if instance.city and not instance.city.location:
        # Get all locations in this city
        from django.contrib.gis.db.models.functions import Centroid

        # Calculate average point of all locations in this city
        locations = Location.objects.filter(city=instance.city)
        if locations.count() >= 5:  # Only update if we have enough data points
            try:
                # Calculate centroid of all location points
                centroid = Location.objects.filter(city=instance.city).aggregate(
                    center=Centroid("coordinates")
                )["center"]

                if centroid:
                    instance.city.location = centroid
                    instance.city.save(update_fields=["location"])
            except Exception as e:
                # Log the error but don't raise exception
                print(f"Error updating city center: {e}")
