import uuid

from django.test import TestCase

from apps.authapp.models import User
from apps.customersapp.models import (
    Customer,
    CustomerPreference,
    FavoriteService,
    FavoriteShop,
    FavoriteSpecialist,
    SavedPaymentMethod,
)


class CustomerModelTest(TestCase):
    """Test case for the Customer model"""

    def setUp(self):
        # Create a user for testing
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

    def test_customer_creation(self):
        """Test creating a customer profile"""
        customer = Customer.objects.create(
            user=self.user, name="Test Customer", city="Riyadh"
        )

        self.assertEqual(customer.user, self.user)
        self.assertEqual(customer.name, "Test Customer")
        self.assertEqual(customer.city, "Riyadh")
        self.assertIsNone(customer.location)
        self.assertIsNone(customer.birth_date)
        self.assertEqual(customer.bio, "")

    def test_customer_string_representation(self):
        """Test the string representation of Customer"""
        customer = Customer.objects.create(user=self.user, name="Test Customer")

        self.assertEqual(str(customer), "1234567890 - Test Customer")

        # Test without name
        customer.name = ""
        customer.save()
        self.assertEqual(str(customer), "1234567890 - Unnamed")


class CustomerPreferenceModelTest(TestCase):
    """Test case for the CustomerPreference model"""

    def setUp(self):
        # Create a user and customer for testing
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")
        self.customer = Customer.objects.create(user=self.user, name="Test Customer")

    def test_preference_creation(self):
        """Test creating customer preferences"""
        prefs = CustomerPreference.objects.create(
            customer=self.customer,
            language="ar",
            notification_enabled=True,
            email_notifications=False,
            appointment_reminder_minutes=45,
        )

        self.assertEqual(prefs.customer, self.customer)
        self.assertEqual(prefs.language, "ar")
        self.assertTrue(prefs.notification_enabled)
        self.assertFalse(prefs.email_notifications)
        self.assertTrue(prefs.sms_notifications)  # Default value
        self.assertTrue(prefs.push_notifications)  # Default value
        self.assertEqual(prefs.appointment_reminder_minutes, 45)

    def test_preference_string_representation(self):
        """Test the string representation of CustomerPreference"""
        prefs = CustomerPreference.objects.create(customer=self.customer)

        self.assertEqual(str(prefs), f"Preferences for {self.customer}")


class SavedPaymentMethodModelTest(TestCase):
    """Test case for the SavedPaymentMethod model"""

    def setUp(self):
        # Create a user and customer for testing
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")
        self.customer = Customer.objects.create(user=self.user, name="Test Customer")

    def test_payment_method_creation(self):
        """Test creating a saved payment method"""
        payment_method = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test123",
            last_digits="1234",
            expiry_month="12",
            expiry_year="2025",
            card_brand="visa",
        )

        self.assertEqual(payment_method.customer, self.customer)
        self.assertEqual(payment_method.payment_type, "card")
        self.assertEqual(payment_method.token, "tok_test123")
        self.assertEqual(payment_method.last_digits, "1234")
        self.assertEqual(payment_method.expiry_month, "12")
        self.assertEqual(payment_method.expiry_year, "2025")
        self.assertEqual(payment_method.card_brand, "visa")
        self.assertTrue(payment_method.is_default)  # First card should be default

    def test_default_payment_method_logic(self):
        """Test default payment method logic"""
        # First payment method should be default
        pm1 = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test123",
            last_digits="1234",
        )

        self.assertTrue(pm1.is_default)

        # Second payment method not marked as default should not be default
        pm2 = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test456",
            last_digits="5678",
            is_default=False,
        )

        self.assertFalse(pm2.is_default)

        # But if we make it default, it should unset the first one
        pm2.is_default = True
        pm2.save()

        # Refresh from database
        pm1.refresh_from_db()
        pm2.refresh_from_db()

        self.assertFalse(pm1.is_default)
        self.assertTrue(pm2.is_default)

    def test_payment_method_string_representation(self):
        """Test the string representation of SavedPaymentMethod"""
        # Card with last digits
        pm1 = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test123",
            last_digits="1234",
        )

        self.assertEqual(str(pm1), f"{self.customer} - Credit/Debit Card (**** 1234)")

        # Other payment type
        pm2 = SavedPaymentMethod.objects.create(
            customer=self.customer, payment_type="stcpay", token="stc_test123"
        )

        self.assertEqual(str(pm2), f"{self.customer} - STC Pay")


class FavoriteEntitiesModelTest(TestCase):
    """Test case for Favorite models (Shop, Specialist, Service)"""

    def setUp(self):
        # Create a user and customer for testing
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")
        self.customer = Customer.objects.create(user=self.user, name="Test Customer")

        # Mock related entities
        self.shop_id = uuid.uuid4()
        self.specialist_id = uuid.uuid4()
        self.service_id = uuid.uuid4()

    def test_favorite_shop_creation(self):
        """Test creating a favorite shop"""
        # Create a mock Shop
        from unittest.mock import MagicMock, patch

        shop_mock = MagicMock()
        shop_mock.id = self.shop_id
        shop_mock.__str__.return_value = "Mock Shop"

        with patch(
            "apps.customersapp.models.FavoriteShop.shop.__get__", return_value=shop_mock
        ):
            favorite = FavoriteShop.objects.create(
                customer=self.customer, shop_id=self.shop_id
            )

            self.assertEqual(favorite.customer, self.customer)
            self.assertEqual(favorite.shop_id, self.shop_id)
            self.assertEqual(str(favorite), f"{self.customer} - Mock Shop")

    def test_favorite_specialist_creation(self):
        """Test creating a favorite specialist"""
        # Create a mock Specialist
        from unittest.mock import MagicMock, patch

        specialist_mock = MagicMock()
        specialist_mock.id = self.specialist_id
        specialist_mock.__str__.return_value = "Mock Specialist"

        with patch(
            "apps.customersapp.models.FavoriteSpecialist.specialist.__get__",
            return_value=specialist_mock,
        ):
            favorite = FavoriteSpecialist.objects.create(
                customer=self.customer, specialist_id=self.specialist_id
            )

            self.assertEqual(favorite.customer, self.customer)
            self.assertEqual(favorite.specialist_id, self.specialist_id)
            self.assertEqual(str(favorite), f"{self.customer} - Mock Specialist")

    def test_favorite_service_creation(self):
        """Test creating a favorite service"""
        # Create a mock Service
        from unittest.mock import MagicMock, patch

        service_mock = MagicMock()
        service_mock.id = self.service_id
        service_mock.__str__.return_value = "Mock Service"

        with patch(
            "apps.customersapp.models.FavoriteService.service.__get__",
            return_value=service_mock,
        ):
            favorite = FavoriteService.objects.create(
                customer=self.customer, service_id=self.service_id
            )

            self.assertEqual(favorite.customer, self.customer)
            self.assertEqual(favorite.service_id, self.service_id)
            self.assertEqual(str(favorite), f"{self.customer} - Mock Service")
