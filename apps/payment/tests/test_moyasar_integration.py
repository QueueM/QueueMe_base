"""
Tests for Moyasar payment integration with multiple wallet types.
"""

import json
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.payment.models import Transaction
from apps.payment.services.moyasar_service import MoyasarService
from apps.payment.views.webhook_views import (
    ads_webhook,
    merchant_webhook,
    subscription_webhook,
)

User = get_user_model()


class MockResponse:
    """Mock response for API calls"""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.json_data = json_data or {}

    def json(self):
        return self.json_data


class MoyasarMultiWalletTest(TestCase):
    """Test the Moyasar integration with multiple wallet types"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword123"
        )
        self.factory = RequestFactory()

        # Store original settings
        self.original_sub_settings = settings.MOYASAR_SUB
        self.original_ads_settings = settings.MOYASAR_ADS
        self.original_mer_settings = settings.MOYASAR_MER

        # Mock wallet settings
        settings.MOYASAR_SUB = {
            "api_key": "sk_test_subscription",
            "public_key": "pk_test_subscription",
            "wallet_id": "wallet_sub_123",
        }
        settings.MOYASAR_ADS = {
            "api_key": "sk_test_ads",
            "public_key": "pk_test_ads",
            "wallet_id": "wallet_ads_123",
        }
        settings.MOYASAR_MER = {
            "api_key": "sk_test_merchant",
            "public_key": "pk_test_merchant",
            "wallet_id": "wallet_merchant_123",
        }

    def tearDown(self):
        # Restore original settings
        settings.MOYASAR_SUB = self.original_sub_settings
        settings.MOYASAR_ADS = self.original_ads_settings
        settings.MOYASAR_MER = self.original_mer_settings

    @mock.patch("requests.post")
    def test_subscription_wallet_payment(self, mock_post):
        """Test creating a payment with the subscription wallet"""
        # Mock successful payment response
        mock_post.return_value = MockResponse(
            201,
            {
                "id": "test_sub_payment",
                "status": "initiated",
                "amount": 10000,  # 100 SAR in halalas
                "source": {"type": "creditcard"},
                "url": "https://pay.moyasar.com/test_sub_payment",
            },
        )

        # Create a payment
        result = MoyasarService.create_payment(
            amount=100,
            payment_type="subscription",
            entity_type="subscription_plan",
            entity_id="test_plan_id",
            user_id=str(self.user.id),
            description="Test Subscription Payment",
            payment_method="creditcard",
            wallet_type="subscription",
            card_data={"token": "test_token"},
            callback_url="https://example.com/callback",
        )

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the correct API key was used
        self.assertEqual(call_args[1]["auth"][0], "sk_test_subscription")

        # Verify result
        self.assertEqual(result["status"], "initiated")
        self.assertTrue("transaction_id" in result)

        # Verify transaction was created with correct wallet type
        transaction = Transaction.objects.get(transaction_id="test_sub_payment")
        self.assertEqual(transaction.wallet_type, "subscription")
        self.assertEqual(transaction.amount, 100)

    @mock.patch("requests.post")
    def test_ads_wallet_payment(self, mock_post):
        """Test creating a payment with the ads wallet"""
        # Mock successful payment response
        mock_post.return_value = MockResponse(
            201,
            {
                "id": "test_ads_payment",
                "status": "initiated",
                "amount": 5000,  # 50 SAR in halalas
                "source": {"type": "creditcard"},
                "url": "https://pay.moyasar.com/test_ads_payment",
            },
        )

        # Create a payment
        result = MoyasarService.create_payment(
            amount=50,
            payment_type="advertisement",
            entity_type="ad_campaign",
            entity_id="test_ad_id",
            user_id=str(self.user.id),
            description="Test Ad Payment",
            payment_method="creditcard",
            wallet_type="ads",
            card_data={"token": "test_token"},
            callback_url="https://example.com/callback",
        )

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the correct API key was used
        self.assertEqual(call_args[1]["auth"][0], "sk_test_ads")

        # Verify result
        self.assertEqual(result["status"], "initiated")
        self.assertTrue("transaction_id" in result)

        # Verify transaction was created with correct wallet type
        transaction = Transaction.objects.get(transaction_id="test_ads_payment")
        self.assertEqual(transaction.wallet_type, "ads")
        self.assertEqual(transaction.amount, 50)

    @mock.patch("requests.post")
    def test_merchant_wallet_payment(self, mock_post):
        """Test creating a payment with the merchant wallet"""
        # Mock successful payment response
        mock_post.return_value = MockResponse(
            201,
            {
                "id": "test_merchant_payment",
                "status": "initiated",
                "amount": 12500,  # 125 SAR in halalas
                "source": {"type": "creditcard"},
                "url": "https://pay.moyasar.com/test_merchant_payment",
            },
        )

        # Create a payment
        result = MoyasarService.create_payment(
            amount=125,
            payment_type="booking",
            entity_type="appointment",
            entity_id="test_booking_id",
            user_id=str(self.user.id),
            description="Test Booking Payment",
            payment_method="creditcard",
            wallet_type="merchant",
            card_data={"token": "test_token"},
            callback_url="https://example.com/callback",
        )

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the correct API key was used
        self.assertEqual(call_args[1]["auth"][0], "sk_test_merchant")

        # Verify result
        self.assertEqual(result["status"], "initiated")
        self.assertTrue("transaction_id" in result)

        # Verify transaction was created with correct wallet type
        transaction = Transaction.objects.get(transaction_id="test_merchant_payment")
        self.assertEqual(transaction.wallet_type, "merchant")
        self.assertEqual(transaction.amount, 125)

    @mock.patch("requests.get")
    def test_verify_payment_uses_correct_wallet(self, mock_get):
        """Test payment verification uses the correct wallet API key"""
        # Create transactions with different wallet types
        subscription_transaction = Transaction.objects.create(
            transaction_id="sub_payment_to_verify",
            user=self.user,
            amount=100,
            payment_method="creditcard",
            status="initiated",
            entity_type="subscription_plan",
            entity_id="test_plan_id",
            payment_type="subscription",
            wallet_type="subscription",
            provider="moyasar",
        )

        ads_transaction = Transaction.objects.create(
            transaction_id="ads_payment_to_verify",
            user=self.user,
            amount=50,
            payment_method="creditcard",
            status="initiated",
            entity_type="ad_campaign",
            entity_id="test_ad_id",
            payment_type="advertisement",
            wallet_type="ads",
            provider="moyasar",
        )

        # Mock response
        mock_get.return_value = MockResponse(
            200,
            {
                "id": "payment_id",
                "status": "paid",
                "amount": 10000,
                "source": {"type": "creditcard"},
            },
        )

        # Verify subscription payment
        MoyasarService.verify_payment("sub_payment_to_verify")

        # Check correct API key was used
        self.assertEqual(mock_get.call_args[1]["auth"][0], "sk_test_subscription")

        # Reset mock
        mock_get.reset_mock()

        # Verify ads payment
        MoyasarService.verify_payment("ads_payment_to_verify")

        # Check correct API key was used
        self.assertEqual(mock_get.call_args[1]["auth"][0], "sk_test_ads")

    @mock.patch("apps.payment.services.moyasar_service.MoyasarService.process_webhook")
    def test_webhook_routing(self, mock_process):
        """Test webhook routing to appropriate processors based on wallet type"""
        # Mock webhook processing
        mock_process.return_value = {"success": True}

        # Test subscription webhook
        request = self.factory.post(
            reverse("subscription_webhook"),
            data=json.dumps({"type": "payment.paid", "data": {"id": "test_payment"}}),
            content_type="application/json",
        )

        response = subscription_webhook(request)
        self.assertEqual(response.status_code, 200)
        mock_process.assert_called_with(
            {"type": "payment.paid", "data": {"id": "test_payment"}},
            {"Signature": None},
            wallet_type="subscription",
        )

        # Reset mock
        mock_process.reset_mock()

        # Test ads webhook
        request = self.factory.post(
            reverse("ads_webhook"),
            data=json.dumps({"type": "payment.paid", "data": {"id": "test_payment"}}),
            content_type="application/json",
        )

        response = ads_webhook(request)
        self.assertEqual(response.status_code, 200)
        mock_process.assert_called_with(
            {"type": "payment.paid", "data": {"id": "test_payment"}},
            {"Signature": None},
            wallet_type="ads",
        )

        # Reset mock
        mock_process.reset_mock()

        # Test merchant webhook
        request = self.factory.post(
            reverse("merchant_webhook"),
            data=json.dumps({"type": "payment.paid", "data": {"id": "test_payment"}}),
            content_type="application/json",
        )

        response = merchant_webhook(request)
        self.assertEqual(response.status_code, 200)
        mock_process.assert_called_with(
            {"type": "payment.paid", "data": {"id": "test_payment"}},
            {"Signature": None},
            wallet_type="merchant",
        )
