from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.authapp.models import User
from apps.customersapp.models import Customer, CustomerPreference
from apps.customersapp.services.preference_extractor import PreferenceExtractor


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    """Create a Customer profile when a new User with type 'customer' is created"""
    if created and instance.user_type == "customer":
        customer = Customer.objects.create(user=instance)
        CustomerPreference.objects.create(customer=customer)


@receiver(post_save, sender=Customer)
def update_user_profile_status(sender, instance, created, **kwargs):
    """Update the user's profile_completed status"""
    if not created and instance.name:
        # If customer has a name, mark profile as completed
        if not instance.user.profile_completed:
            instance.user.profile_completed = True
            instance.user.save(update_fields=["profile_completed"])


@receiver(post_save, sender="bookingapp.Appointment")
def update_customer_preferences(sender, instance, created, **kwargs):
    """Update customer preferences based on appointment data"""
    if created:
        try:
            # Extract category preferences from this booking
            PreferenceExtractor.update_from_appointment(instance)
        except Exception as e:
            # Log the error but don't break the save
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error updating preferences: {e}")
