import uuid
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.bookingapp.models import Appointment

from ..models import PaymentMethod, Transaction


class PaymentViewSetTest(TestCase):
    def setUp(self):
        # Create test users
        self.customer = User.objects.create_user(
            phone_number="+1234567890", user_type="customer"
        )

        self.admin = User.objects.create_user(
            phone_number="+0987654321", user_type="admin", is_staff=True
        )

        # Set up API client
        self.client = APIClient()

        # Set up content type for test objects
        self.content_type = ContentType.objects.get_for_model(Appointment)
        self.object_id = uuid.uuid4()

        # Create a payment method for the customer
        self.payment_method = PaymentMethod.objects.create(
            user=self.customer,
            type="card",
            token="tok_visa_123456",
            last_digits="1234",
            expiry_month="12",
            expiry_year="2025",
            card_brand="visa",
            is_default=True,
        )

        # Create a test transaction
        self.transaction = Transaction.objects.create(
            user=self.customer,
            amount=100.00,
            amount_halalas=10000,
            payment_method=self.payment_method,
            payment_type="card",
            status="succeeded",
            transaction_type="booking",
            content_type=self.content_type,
            object_id=self.object_id,
        )

    def test_payment_methods_list(self):
        """Test listing customer's payment methods"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        url = reverse("payment-payment-methods")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.payment_method.id))

    @patch("payment.services.payment_service.PaymentService.add_payment_method")
    def test_add_payment_method(self, mock_add_payment_method):
        """Test adding a new payment method"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Mock the service response
        mock_add_payment_method.return_value = {
            "success": True,
            "payment_method_id": str(uuid.uuid4()),
            "type": "card",
            "is_default": True,
        }

        url = reverse("payment-add-payment-method")
        data = {"token": "tok_visa_new", "payment_type": "card", "make_default": True}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_add_payment_method.assert_called_once()

    @patch("payment.services.payment_service.PaymentService.create_payment")
    def test_create_payment(self, mock_create_payment):
        """Test creating a payment transaction"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Mock the service response
        transaction_id = uuid.uuid4()
        mock_create_payment.return_value = {
            "success": True,
            "transaction_id": str(transaction_id),
            "status": "initiated",
            "redirect_url": "https://test.url",
        }

        url = reverse("payment-create-payment")
        data = {
            "amount": 150.00,
            "transaction_type": "booking",
            "description": "Test payment",
            "payment_method_id": str(self.payment_method.id),
            "content_type": {"app_label": "bookingapp", "model": "appointment"},
            "object_id": str(self.object_id),
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["transaction_id"], str(transaction_id))
        self.assertEqual(response.data["status"], "initiated")
        self.assertEqual(response.data["redirect_url"], "https://test.url")

        # Check service was called with correct arguments
        mock_create_payment.assert_called_once()
        call_args = mock_create_payment.call_args[1]
        self.assertEqual(call_args["user_id"], self.customer.id)
        self.assertEqual(call_args["amount"], 150.00)
        self.assertEqual(call_args["transaction_type"], "booking")

    @patch("payment.services.payment_service.PaymentService.create_refund")
    def test_create_refund(self, mock_create_refund):
        """Test creating a refund"""
        # Authenticate as admin (required for refunds)
        self.client.force_authenticate(user=self.admin)

        # Mock the service response
        refund_id = uuid.uuid4()
        mock_create_refund.return_value = {
            "success": True,
            "refund_id": str(refund_id),
            "status": "succeeded",
            "amount": "50.00",
        }

        url = reverse("payment-create-refund")
        data = {
            "transaction_id": str(self.transaction.id),
            "amount": 50.00,
            "reason": "Test refund",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["refund_id"], str(refund_id))
        self.assertEqual(response.data["status"], "succeeded")
        self.assertEqual(response.data["amount"], "50.00")

        # Check service was called with correct arguments
        mock_create_refund.assert_called_once()
        call_args = mock_create_refund.call_args[1]
        self.assertEqual(str(call_args["transaction_id"]), str(self.transaction.id))
        self.assertEqual(call_args["amount"], 50.00)
        self.assertEqual(call_args["reason"], "Test refund")

    def test_recommend_payment_method(self):
        """Test payment method recommendation endpoint"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        url = reverse("payment-recommend-payment-method")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))

        # Should include our payment method
        has_our_method = False
        for method in response.data:
            if "id" in method and method["id"] == str(self.payment_method.id):
                has_our_method = True
                break

        self.assertTrue(has_our_method)
