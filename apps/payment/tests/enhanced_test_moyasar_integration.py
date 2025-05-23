"""
Enhanced Moyasar integration tests for QueueMe backend

This module provides comprehensive test coverage for the Moyasar payment integration,
including edge cases, error handling, and webhook validation.
"""

import json
import uuid
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authapp.models import User
from apps.payment.models import PaymentMethod, Transaction
from apps.payment.services.moyasar_service import MoyasarService
from apps.payment.views import merchant_webhook


class MockResponse:
    """Mock response object for requests library"""

    def __init__(self, status_code, json_data, headers=None):
        self.status_code = status_code
        self.json_data = json_data
        self.headers = headers or {}

    def json(self):
        return self.json_data


class EnhancedMoyasarIntegrationTest(TestCase):
    """
    Enhanced test cases for Moyasar payment integration.

    This test suite provides comprehensive coverage for:
    - Payment creation across all wallet types
    - Payment verification and status updates
    - Error handling and retry mechanisms
    - Webhook processing and validation
    - Security and signature verification
    """

    def setUp(self):
        """Set up test environment"""
        self.factory = RequestFactory()
        self.user = User.objects.create(
            phone_number="966501234567",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        # Create payment method for testing
        self.payment_method = PaymentMethod.objects.create(
            user=self.user,
            type="creditcard",
            token="tok_test_valid",
            last_digits="1234",
            is_default=True,
        )

        # Set up API key patch
        self.moyasar_api_keys_patcher = mock.patch(
            "apps.payment.services.moyasar_service.settings.MOYASAR_API_KEYS",
            {
                "merchant": "sk_test_merchant",
                "subscription": "sk_test_subscription",
                "ads": "sk_test_ads",
            },
        )
        self.moyasar_api_keys_patcher.start()
        self.addCleanup(self.moyasar_api_keys_patcher.stop)

        # Set up webhook secret patch
        self.moyasar_webhook_secrets_patcher = mock.patch(
            "apps.payment.services.moyasar_service.settings.MOYASAR_WEBHOOK_SECRETS",
            {
                "merchant": "whsec_merchant_test",
                "subscription": "whsec_subscription_test",
                "ads": "whsec_ads_test",
            },
        )
        self.moyasar_webhook_secrets_patcher.start()
        self.addCleanup(self.moyasar_webhook_secrets_patcher.stop)

    @mock.patch("requests.post")
    def test_create_payment_success_all_wallet_types(self, mock_post):
        """Test successful payment creation for all wallet types"""
        # Test data for different wallet types
        test_cases = [
            {
                "wallet_type": "merchant",
                "payment_type": "booking",
                "entity_type": "appointment",
                "entity_id": "test_booking_id",
                "amount": 125,
                "expected_api_key": "sk_test_merchant",
                "transaction_id": "test_merchant_payment",
            },
            {
                "wallet_type": "subscription",
                "payment_type": "subscription",
                "entity_type": "subscription_plan",
                "entity_id": "test_plan_id",
                "amount": 299,
                "expected_api_key": "sk_test_subscription",
                "transaction_id": "test_subscription_payment",
            },
            {
                "wallet_type": "ads",
                "payment_type": "advertisement",
                "entity_type": "ad_campaign",
                "entity_id": "test_ad_id",
                "amount": 199,
                "expected_api_key": "sk_test_ads",
                "transaction_id": "test_ads_payment",
            },
        ]

        for case in test_cases:
            # Reset mock for each test case
            mock_post.reset_mock()

            # Mock response
            mock_post.return_value = MockResponse(
                200,
                {
                    "id": case["transaction_id"],
                    "status": "initiated",
                    "amount": case["amount"] * 100,  # Moyasar uses halalas
                    "source": {"type": "creditcard"},
                },
            )

            # Create payment
            result = MoyasarService.create_payment(
                amount=case["amount"],
                payment_type=case["payment_type"],
                entity_type=case["entity_type"],
                entity_id=case["entity_id"],
                user_id=str(self.user.id),
                description=f"Test {case['payment_type'].title()} Payment",
                payment_method="creditcard",
                wallet_type=case["wallet_type"],
                card_data={"token": "test_token"},
                callback_url="https://example.com/callback",
            )

            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check that the correct API key was used
            self.assertEqual(call_args[1]["auth"][0], case["expected_api_key"])

            # Verify result
            self.assertEqual(result["status"], "initiated")
            self.assertTrue("transaction_id" in result)

            # Verify transaction was created with correct wallet type
            transaction = Transaction.objects.get(transaction_id=case["transaction_id"])
            self.assertEqual(transaction.wallet_type, case["wallet_type"])
            self.assertEqual(transaction.amount, case["amount"])
            self.assertEqual(transaction.entity_type, case["entity_type"])
            self.assertEqual(transaction.entity_id, case["entity_id"])

    @mock.patch("requests.post")
    def test_create_payment_error_handling(self, mock_post):
        """Test error handling during payment creation"""
        # Test cases for different error scenarios
        test_cases = [
            {
                "scenario": "API error",
                "status_code": 400,
                "response": {"message": "Invalid card token"},
                "expected_exception": ValueError,
            },
            {
                "scenario": "Server error",
                "status_code": 500,
                "response": {"message": "Internal server error"},
                "expected_exception": ValueError,
            },
            {
                "scenario": "Network error",
                "exception": ConnectionError("Connection refused"),
                "expected_exception": ConnectionError,
            },
        ]

        for case in test_cases:
            # Reset mock for each test case
            mock_post.reset_mock()

            if "exception" in case:
                # Mock exception
                mock_post.side_effect = case["exception"]
            else:
                # Mock error response
                mock_post.return_value = MockResponse(
                    case["status_code"], case["response"]
                )

            # Attempt to create payment and verify exception
            with self.assertRaises(case["expected_exception"]):
                MoyasarService.create_payment(
                    amount=100,
                    payment_type="booking",
                    entity_type="appointment",
                    entity_id="test_booking_id",
                    user_id=str(self.user.id),
                    description="Test Error Payment",
                    payment_method="creditcard",
                    wallet_type="merchant",
                    card_data={"token": "test_token"},
                    callback_url="https://example.com/callback",
                )

    @mock.patch("requests.get")
    def test_verify_payment_status_transitions(self, mock_get):
        """Test payment verification and status transitions"""
        # Create a transaction to verify
        transaction = Transaction.objects.create(
            transaction_id="payment_to_verify",
            user=self.user,
            amount=100,
            payment_method="creditcard",
            status="initiated",
            entity_type="appointment",
            entity_id="test_booking_id",
            payment_type="booking",
            wallet_type="merchant",
            provider="moyasar",
        )

        # Test cases for different payment statuses
        test_cases = [
            {
                "moyasar_status": "paid",
                "expected_status": "succeeded",
            },
            {
                "moyasar_status": "failed",
                "expected_status": "failed",
            },
            {
                "moyasar_status": "authorized",
                "expected_status": "authorized",
            },
            {
                "moyasar_status": "captured",
                "expected_status": "succeeded",
            },
            {
                "moyasar_status": "voided",
                "expected_status": "cancelled",
            },
            {
                "moyasar_status": "refunded",
                "expected_status": "refunded",
            },
        ]

        for case in test_cases:
            # Reset mock and transaction for each test case
            mock_get.reset_mock()
            transaction.status = "initiated"
            transaction.save()

            # Mock response
            mock_get.return_value = MockResponse(
                200,
                {
                    "id": "payment_to_verify",
                    "status": case["moyasar_status"],
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            # Verify payment
            result = MoyasarService.verify_payment("payment_to_verify")

            # Refresh transaction from database
            transaction.refresh_from_db()

            # Verify status transition
            self.assertEqual(transaction.status, case["expected_status"])
            self.assertEqual(result["status"], case["expected_status"])

    @mock.patch("requests.get")
    def test_verify_payment_error_handling(self, mock_get):
        """Test error handling during payment verification"""
        # Create a transaction to verify
        transaction = Transaction.objects.create(
            transaction_id="payment_error_verify",
            user=self.user,
            amount=100,
            payment_method="creditcard",
            status="initiated",
            entity_type="appointment",
            entity_id="test_booking_id",
            payment_type="booking",
            wallet_type="merchant",
            provider="moyasar",
        )

        # Test cases for different error scenarios
        test_cases = [
            {
                "scenario": "Payment not found",
                "status_code": 404,
                "response": {"message": "Payment not found"},
                "expected_exception": ValueError,
            },
            {
                "scenario": "Server error",
                "status_code": 500,
                "response": {"message": "Internal server error"},
                "expected_exception": ValueError,
            },
            {
                "scenario": "Network error",
                "exception": ConnectionError("Connection refused"),
                "expected_exception": ConnectionError,
            },
        ]

        for case in test_cases:
            # Reset mock for each test case
            mock_get.reset_mock()

            if "exception" in case:
                # Mock exception
                mock_get.side_effect = case["exception"]
            else:
                # Mock error response
                mock_get.return_value = MockResponse(
                    case["status_code"], case["response"]
                )

            # Attempt to verify payment and verify exception
            with self.assertRaises(case["expected_exception"]):
                MoyasarService.verify_payment("payment_error_verify")

            # Verify transaction status remains unchanged
            transaction.refresh_from_db()
            self.assertEqual(transaction.status, "initiated")

    @mock.patch(
        "apps.payment.services.moyasar_service.MoyasarService.verify_webhook_signature"
    )
    def test_webhook_signature_verification(self, mock_verify):
        """Test webhook signature verification"""
        # Test cases for different signature scenarios
        test_cases = [
            {
                "scenario": "Valid signature",
                "signature": "valid_signature",
                "verification_result": True,
                "expected_status": 200,
            },
            {
                "scenario": "Invalid signature",
                "signature": "invalid_signature",
                "verification_result": False,
                "expected_status": 403,
            },
            {
                "scenario": "Missing signature",
                "signature": None,
                "verification_result": False,
                "expected_status": 403,
            },
        ]

        for case in test_cases:
            # Reset mock for each test case
            mock_verify.reset_mock()

            # Mock signature verification
            mock_verify.return_value = case["verification_result"]

            # Create request with webhook payload
            headers = {}
            if case["signature"]:
                headers["HTTP_SIGNATURE"] = case["signature"]

            request = self.factory.post(
                reverse("merchant_webhook"),
                data=json.dumps(
                    {"type": "payment.paid", "data": {"id": "test_payment"}}
                ),
                content_type="application/json",
                **headers,
            )

            # Process webhook
            response = merchant_webhook(request)

            # Verify response status
            self.assertEqual(response.status_code, case["expected_status"])

            # Verify signature verification was called if signature was provided
            if case["signature"]:
                mock_verify.assert_called_once()
            else:
                mock_verify.assert_not_called()

    @mock.patch("apps.payment.services.moyasar_service.MoyasarService.process_webhook")
    def test_webhook_event_handling(self, mock_process):
        """Test handling of different webhook event types"""
        # Test cases for different event types
        test_cases = [
            {
                "event_type": "payment.paid",
                "expected_status": "succeeded",
            },
            {
                "event_type": "payment.failed",
                "expected_status": "failed",
            },
            {
                "event_type": "payment.refunded",
                "expected_status": "refunded",
            },
            {
                "event_type": "payment.captured",
                "expected_status": "succeeded",
            },
            {
                "event_type": "payment.voided",
                "expected_status": "cancelled",
            },
            {
                "event_type": "unknown.event",
                "expected_status": None,  # Should be ignored
            },
        ]

        for case in test_cases:
            # Reset mock for each test case
            mock_process.reset_mock()

            # Mock webhook processing
            if case["expected_status"]:
                mock_process.return_value = {
                    "success": True,
                    "status": case["expected_status"],
                }
            else:
                mock_process.return_value = {
                    "success": False,
                    "error": "Unknown event type",
                }

            # Create request with webhook payload
            request = self.factory.post(
                reverse("merchant_webhook"),
                data=json.dumps(
                    {"type": case["event_type"], "data": {"id": "test_payment"}}
                ),
                content_type="application/json",
            )

            # Process webhook
            response = merchant_webhook(request)

            # Verify response
            self.assertEqual(response.status_code, 200)

            # Verify webhook processing was called
            mock_process.assert_called_once()

            # Verify correct event type was passed
            self.assertEqual(mock_process.call_args[0][0]["type"], case["event_type"])

    @mock.patch("requests.get")
    def test_payment_verification_retry_mechanism(self, mock_get):
        """Test payment verification retry mechanism for transient errors"""
        # Create a transaction to verify
        transaction = Transaction.objects.create(
            transaction_id="payment_retry_verify",
            user=self.user,
            amount=100,
            payment_method="creditcard",
            status="initiated",
            entity_type="appointment",
            entity_id="test_booking_id",
            payment_type="booking",
            wallet_type="merchant",
            provider="moyasar",
        )

        # Mock responses for retry sequence
        mock_responses = [
            # First attempt - server error
            MockResponse(500, {"message": "Internal server error"}),
            # Second attempt - success
            MockResponse(
                200,
                {
                    "id": "payment_retry_verify",
                    "status": "paid",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            ),
        ]

        mock_get.side_effect = mock_responses

        # Patch the retry settings to speed up the test
        with mock.patch(
            "apps.payment.services.moyasar_service.VERIFICATION_RETRY_DELAY", 0.01
        ):
            with mock.patch(
                "apps.payment.services.moyasar_service.MAX_VERIFICATION_RETRIES", 3
            ):
                # Verify payment with retry
                result = MoyasarService.verify_payment_with_retry(
                    "payment_retry_verify"
                )

        # Verify the function was called twice
        self.assertEqual(mock_get.call_count, 2)

        # Verify transaction status was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "succeeded")
        self.assertEqual(result["status"], "succeeded")

    @mock.patch("requests.post")
    def test_create_payment_with_saved_card(self, mock_post):
        """Test payment creation with saved card"""
        # Mock response
        mock_post.return_value = MockResponse(
            200,
            {
                "id": "saved_card_payment",
                "status": "initiated",
                "amount": 15000,
                "source": {"type": "creditcard"},
            },
        )

        # Create payment with saved card
        result = MoyasarService.create_payment(
            amount=150,
            payment_type="booking",
            entity_type="appointment",
            entity_id="test_booking_id",
            user_id=str(self.user.id),
            description="Test Saved Card Payment",
            payment_method="saved_card",
            wallet_type="merchant",
            saved_card_id=str(self.payment_method.id),
            callback_url="https://example.com/callback",
        )

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the correct API key was used
        self.assertEqual(call_args[1]["auth"][0], "sk_test_merchant")

        # Check that the correct card token was used
        self.assertEqual(
            call_args[1]["json"]["source"]["token"], self.payment_method.token
        )

        # Verify result
        self.assertEqual(result["status"], "initiated")
        self.assertTrue("transaction_id" in result)

        # Verify transaction was created
        transaction = Transaction.objects.get(transaction_id="saved_card_payment")
        self.assertEqual(transaction.wallet_type, "merchant")
        self.assertEqual(transaction.amount, 150)
        self.assertEqual(transaction.payment_method, "saved_card")

    def test_transaction_idempotency(self):
        """Test transaction idempotency to prevent duplicate payments"""
        # Create a unique idempotency key
        idempotency_key = str(uuid.uuid4())

        # Create first transaction with idempotency key
        transaction1 = Transaction.objects.create(
            transaction_id="idempotent_payment_1",
            user=self.user,
            amount=100,
            payment_method="creditcard",
            status="initiated",
            entity_type="appointment",
            entity_id="test_booking_id",
            payment_type="booking",
            wallet_type="merchant",
            provider="moyasar",
            idempotency_key=idempotency_key,
        )

        # Attempt to create second transaction with same idempotency key
        with mock.patch("requests.post") as mock_post:
            # Mock response
            mock_post.return_value = MockResponse(
                200,
                {
                    "id": "idempotent_payment_2",
                    "status": "initiated",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            # Create payment with same idempotency key
            result = MoyasarService.create_payment(
                amount=100,
                payment_type="booking",
                entity_type="appointment",
                entity_id="test_booking_id",
                user_id=str(self.user.id),
                description="Test Idempotent Payment",
                payment_method="creditcard",
                wallet_type="merchant",
                card_data={"token": "test_token"},
                callback_url="https://example.com/callback",
                idempotency_key=idempotency_key,
            )

        # Verify result contains original transaction ID
        self.assertEqual(result["transaction_id"], "idempotent_payment_1")

        # Verify no new transaction was created
        self.assertEqual(
            Transaction.objects.filter(idempotency_key=idempotency_key).count(), 1
        )
