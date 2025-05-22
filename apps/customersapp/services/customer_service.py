import logging

from django.db import transaction

from apps.customersapp.models import Customer, CustomerPreference
from apps.geoapp.models import Location

logger = logging.getLogger(__name__)


class CustomerService:
    """
    Service class for handling customer profile operations
    """

    @staticmethod
    @transaction.atomic
    def create_customer(user, name=None, city=None, location_data=None):
        """
        Create a customer profile for a user
        """
        if user.user_type != "customer":
            raise ValueError("User must be of type 'customer'")

        # Check if customer already exists
        try:
            return user.customer_profile
        except Customer.DoesNotExist:
            pass

        # Create location if data provided
        location = None
        if location_data:
            try:
                location = Location.objects.create(**location_data)
            except Exception as e:
                logger.error(f"Error creating location for customer: {e}")

        # Create customer profile
        customer = Customer.objects.create(
            user=user, name=name, city=city, location=location
        )

        # Create default preferences
        CustomerPreference.objects.create(customer=customer)

        return customer

    @staticmethod
    def get_customer_by_phone(phone_number):
        """
        Get a customer by phone number
        """
        from apps.authapp.models import User

        try:
            user = User.objects.get(phone_number=phone_number, user_type="customer")
            return user.customer_profile
        except (User.DoesNotExist, Customer.DoesNotExist):
            return None

    @staticmethod
    def update_customer_profile(customer, data):
        """
        Update customer profile with provided data
        """
        # Update customer fields
        for field in ["name", "city", "birth_date", "bio"]:
            if field in data:
                setattr(customer, field, data[field])

        # Handle avatar separately if provided
        if "avatar" in data and data["avatar"]:
            customer.avatar = data["avatar"]

        # Update location if provided
        if "location" in data and data["location"]:
            location_data = data["location"]

            if customer.location:
                # Update existing location
                for field, value in location_data.items():
                    setattr(customer.location, field, value)
                customer.location.save()
            else:
                # Create new location
                location = Location.objects.create(**location_data)
                customer.location = location

        # Save customer changes
        customer.save()

        # Update preferences if provided
        if (
            "preferences" in data
            and data["preferences"]
            and hasattr(customer, "preferences")
        ):
            preferences = customer.preferences
            preferences_data = data["preferences"]

            for field, value in preferences_data.items():
                if hasattr(preferences, field):
                    setattr(preferences, field, value)

            preferences.save()

        return customer

    @staticmethod
    @transaction.atomic
    def delete_customer_data(customer):
        """
        Delete a customer and all related data
        For GDPR/privacy compliance
        """
        user = customer.user

        # Delete all related customer data
        # This assumes cascade deletion for most related models

        # Manual delete for some relations if necessary
        if hasattr(customer, "preferences"):
            customer.preferences.delete()

        # Delete saved payment methods
        customer.payment_methods.all().delete()

        # Delete customer profile
        customer.delete()

        # Anonymize user instead of deleting to maintain referential integrity
        user.phone_number = f"DELETED_{user.id}"
        user.is_active = False
        user.save()

        return True

    @staticmethod
    def get_customer_booking_history(customer, limit=10):
        """
        Get customer's booking history
        """
        from apps.bookingapp.models import Appointment

        return Appointment.objects.filter(customer=customer.user).order_by(
            "-start_time"
        )[:limit]

    @staticmethod
    def get_customer_favorite_entities(customer):
        """
        Get all customer favorites (shops, specialists, services)
        """
        return {
            "shops": customer.favorite_shops.all().select_related("shop"),
            "specialists": customer.favorite_specialists.all().select_related(
                "specialist"
            ),
            "services": customer.favorite_services.all().select_related("service"),
        }
