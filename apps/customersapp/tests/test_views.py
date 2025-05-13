import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.authapp.models import User
from apps.customersapp.models import Customer, CustomerPreference, FavoriteShop, SavedPaymentMethod


class CustomerViewSetTest(APITestCase):
    """Test case for the CustomerViewSet"""

    def setUp(self):
        # Create a customer user for testing
        self.customer_user = User.objects.create_user(
            phone_number="1234567890", user_type="customer", is_verified=True
        )
        self.customer = Customer.objects.create(
            user=self.customer_user, name="Test Customer", city="Riyadh"
        )
        CustomerPreference.objects.create(customer=self.customer)

        # Create admin user for testing
        self.admin_user = User.objects.create_user(
            phone_number="9876543210",
            user_type="admin",
            is_verified=True,
            is_staff=True,
        )

        # Set up the API client
        self.client = APIClient()

    def test_me_endpoint_unauthorized(self):
        """Test that unauthorized users cannot access the me endpoint"""
        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_customer(self):
        """Test that a customer can access their profile"""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Customer")
        self.assertEqual(response.data["city"], "Riyadh")

    def test_me_endpoint_admin(self):
        """Test that non-customers cannot access the me endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_preferences(self):
        """Test updating customer preferences"""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse("customer-update-preferences")

        data = {
            "language": "ar",
            "notification_enabled": False,
            "appointment_reminder_minutes": 60,
        }

        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        prefs = CustomerPreference.objects.get(customer=self.customer)

        self.assertEqual(prefs.language, "ar")
        self.assertFalse(prefs.notification_enabled)
        self.assertEqual(prefs.appointment_reminder_minutes, 60)


class PaymentMethodViewSetTest(APITestCase):
    """Test case for the PaymentMethodViewSet"""

    def setUp(self):
        # Create a customer user for testing
        self.customer_user = User.objects.create_user(
            phone_number="1234567890", user_type="customer", is_verified=True
        )
        self.customer = Customer.objects.create(user=self.customer_user, name="Test Customer")

        # Create an existing payment method
        self.payment_method = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test123",
            last_digits="1234",
            expiry_month="12",
            expiry_year="2025",
            card_brand="visa",
        )

        # Set up the API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer_user)

    def test_list_payment_methods(self):
        """Test listing payment methods"""
        url = reverse("payment-method-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["payment_type"], "card")
        self.assertEqual(response.data[0]["last_digits"], "1234")

    def test_create_payment_method(self):
        """Test creating a payment method (mock the PaymentMethodService)"""
        url = reverse("payment-method-list")

        # Mock the payment service
        from unittest.mock import patch

        with patch(
            "apps.customersapp.services.payment_method_service.PaymentMethodService.validate_payment_token"
        ) as mock_validate:
            mock_validate.return_value = True

            data = {
                "payment_type": "card",
                "token": "tok_test456",
                "last_digits": "5678",
                "expiry_month": "10",
                "expiry_year": "2026",
                "card_brand": "mastercard",
                "is_default": True,
            }

            response = self.client.post(url, data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_set_default_payment_method(self):
        """Test setting a payment method as default"""
        # Create a second payment method
        second_method = SavedPaymentMethod.objects.create(
            customer=self.customer,
            payment_type="card",
            token="tok_test456",
            last_digits="5678",
            is_default=False,
        )

        url = reverse("payment-method-set-default", args=[second_method.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.payment_method.refresh_from_db()
        second_method.refresh_from_db()

        # Verify default status
        self.assertFalse(self.payment_method.is_default)
        self.assertTrue(second_method.is_default)


class FavoritesViewSetTest(APITestCase):
    """Test case for the FavoritesViewSet"""

    def setUp(self):
        # Create a customer user for testing
        self.customer_user = User.objects.create_user(
            phone_number="1234567890", user_type="customer", is_verified=True
        )
        self.customer = Customer.objects.create(user=self.customer_user, name="Test Customer")

        # Generate IDs for mock entities
        self.shop_id = uuid.uuid4()
        self.specialist_id = uuid.uuid4()
        self.service_id = uuid.uuid4()

        # Set up the API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer_user)

    def test_add_favorite_shop(self):
        """Test adding a shop to favorites"""
        url = reverse("favorites-add-shop")

        # Mock the get_object_or_404 to return a mock shop
        from unittest.mock import MagicMock, patch

        mock_shop = MagicMock()
        mock_shop.id = self.shop_id

        with patch("apps.customersapp.views.get_object_or_404", return_value=mock_shop):
            data = {"shop_id": str(self.shop_id)}
            response = self.client.post(url, data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # Check that favorite was created
            self.assertTrue(
                FavoriteShop.objects.filter(customer=self.customer, shop_id=self.shop_id).exists()
            )

    def test_remove_favorite_shop(self):
        """Test removing a shop from favorites"""
        # Create a favorite first
        favorite = FavoriteShop.objects.create(customer=self.customer, shop_id=self.shop_id)

        url = reverse("favorites-remove-shop")
        data = {"shop_id": str(self.shop_id)}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that favorite was deleted
        self.assertFalse(
            FavoriteShop.objects.filter(customer=self.customer, shop_id=self.shop_id).exists()
        )

    def test_get_favorite_shops(self):
        """Test getting favorite shops"""
        # Create a favorite
        favorite = FavoriteShop.objects.create(customer=self.customer, shop_id=self.shop_id)

        # Mock the related shop
        from unittest.mock import MagicMock, patch

        mock_shop = MagicMock()
        mock_shop.id = self.shop_id
        mock_shop.name = "Test Shop"

        with patch("apps.customersapp.models.FavoriteShop.shop.__get__", return_value=mock_shop):
            url = reverse("favorites-shops")
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)
