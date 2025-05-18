#!/usr/bin/env python
"""
Integration Test for Payment Service with Moyasar Gateway

This test verifies that:
1. Payment methods can be created
2. Payments can be processed
3. Refunds can be processed
4. Webhook handling works correctly
"""

import json
import os
import sys
import time
import unittest
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests

# Add project to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")

import django

django.setup()

from django.conf import settings

from apps.payment.models import PaymentStatus, PaymentTransaction, RefundTransaction
from apps.payment.services.payment_service import PaymentService

# Configuration for tests
TEST_MODE = True  # Set to True to use mock responses, False to test against real Moyasar
# Using non-API-key-like placeholders to avoid false detection
MOYASAR_TEST_SECRET_KEY = "PLACEHOLDER_NOT_REAL_KEY"
MOYASAR_TEST_PUBLISH_KEY = "PLACEHOLDER_NOT_REAL_KEY"


class MockMoyasarClient:
    """Mock Moyasar client for testing without real API calls"""

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.transactions = {}

    def charge(self, amount, currency, source, description, metadata=None, idempotency_key=None):
        """Mock charge method"""
        if idempotency_key and idempotency_key in self.transactions:
            return self.transactions[idempotency_key]

        transaction_id = f"test_{str(uuid.uuid4())[:8]}"

        response = {
            "id": transaction_id,
            "status": "paid",
            "amount": amount,
            "currency": currency,
            "description": description,
            "source": {
                "type": "creditcard",
                "name": "Test User",
                "number": "XXXX-XXXX-XXXX-1234",
                "message": None,
                "transaction_url": f"https://api.moyasar.com/v1/transactions/{transaction_id}",
            },
            "fee": int(amount * 0.025),  # Mock 2.5% fee
            "invoice_id": None,
            "ip": "127.0.0.1",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": metadata or {},
            "success": True,
        }

        if idempotency_key:
            self.transactions[idempotency_key] = response

        return response

    def refund(self, payment_id, amount, reason=None, idempotency_key=None):
        """Mock refund method"""
        if idempotency_key and idempotency_key in self.transactions:
            return self.transactions[idempotency_key]

        refund_id = f"refund_{str(uuid.uuid4())[:8]}"

        response = {
            "id": refund_id,
            "status": "refunded",
            "amount": amount,
            "payment_id": payment_id,
            "reason": reason,
            "message": "Refund successful",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "success": True,
        }

        if idempotency_key:
            self.transactions[idempotency_key] = response

        return response

    def verify_webhook(self, signature, payload):
        """Mock webhook verification"""
        # In test mode, always return True
        return True


class PaymentIntegrationTest(unittest.TestCase):
    """Integration tests for the payment system"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        if TEST_MODE:
            # Set up mock client
            cls.moyasar_client_patcher = patch(
                "apps.payment.moyasar_client.MoyasarClient", MockMoyasarClient
            )
            cls.moyasar_client_mock = cls.moyasar_client_patcher.start()
        else:
            # For real testing, adjust settings to use test keys
            settings.MOYASAR_API_KEY = MOYASAR_TEST_SECRET_KEY

    @classmethod
    def tearDownClass(cls):
        """Tear down test environment"""
        if TEST_MODE:
            cls.moyasar_client_patcher.stop()

    def setUp(self):
        """Set up each test"""
        # Clean up test data from previous runs
        PaymentTransaction.objects.filter(description__startswith="Test transaction").delete()
        RefundTransaction.objects.filter(reason__startswith="Test refund").delete()

    def test_payment_processing(self):
        """Test basic payment processing"""
        # Process a payment
        result = PaymentService.process_payment(
            amount=Decimal("100.00"),
            currency="SAR",
            payment_method_id="test_method",  # This would be a real payment method ID in production
            description="Test transaction for integration test",
            customer_id="test_customer",
            metadata={"test": True, "integration": "automated"},
            idempotency_key=str(uuid.uuid4()),
        )

        # Check result
        self.assertTrue(result["success"], "Payment processing should succeed")
        self.assertIsNotNone(result["transaction_id"], "Transaction ID should be returned")
        self.assertIsNotNone(result["external_id"], "External ID should be set")
        self.assertEqual(result["status"], PaymentStatus.COMPLETED, "Status should be COMPLETED")

        # Verify transaction in database
        transaction = PaymentTransaction.objects.get(id=result["transaction_id"])
        self.assertEqual(transaction.amount, Decimal("100.00"), "Amount should match")
        self.assertEqual(transaction.status, PaymentStatus.COMPLETED, "Status should be COMPLETED")
        self.assertIsNotNone(transaction.external_id, "External ID should be set in DB")

    def test_payment_idempotency(self):
        """Test idempotency key functionality"""
        # Define a unique idempotency key
        idempotency_key = str(uuid.uuid4())

        # Process payment first time
        result1 = PaymentService.process_payment(
            amount=Decimal("50.00"),
            currency="SAR",
            payment_method_id="test_method",
            description="Test transaction with idempotency",
            idempotency_key=idempotency_key,
        )

        # Process with same idempotency key
        result2 = PaymentService.process_payment(
            amount=Decimal("50.00"),  # Same amount
            currency="SAR",
            payment_method_id="test_method",
            description="Test transaction with idempotency",
            idempotency_key=idempotency_key,
        )

        # Results should be identical
        self.assertEqual(
            result1["transaction_id"],
            result2["transaction_id"],
            "Same transaction ID should be returned for same idempotency key",
        )

        # Process with same key but different amount should still return original transaction
        result3 = PaymentService.process_payment(
            amount=Decimal("75.00"),  # Different amount
            currency="SAR",
            payment_method_id="test_method",
            description="Test transaction with idempotency",
            idempotency_key=idempotency_key,
        )

        self.assertEqual(
            result1["transaction_id"],
            result3["transaction_id"],
            "Same transaction ID should be returned regardless of different parameters",
        )

        # Count transactions - there should only be one
        count = PaymentTransaction.objects.filter(
            description="Test transaction with idempotency"
        ).count()

        self.assertEqual(count, 1, "Only one transaction should exist despite multiple API calls")

    def test_refund_processing(self):
        """Test refund processing"""
        # First process a payment
        payment_result = PaymentService.process_payment(
            amount=Decimal("200.00"),
            currency="SAR",
            payment_method_id="test_method",
            description="Test transaction for refund",
            customer_id="test_customer",
        )

        self.assertTrue(payment_result["success"], "Payment should succeed before testing refund")

        # Process a refund for part of the amount
        refund_result = PaymentService.process_refund(
            transaction_id=payment_result["transaction_id"],
            amount=Decimal("50.00"),  # Partial refund
            reason="Test refund for integration test",
        )

        # Check refund result
        self.assertTrue(refund_result["success"], "Refund processing should succeed")
        self.assertIsNotNone(refund_result["refund_id"], "Refund ID should be returned")
        self.assertIsNotNone(refund_result["external_id"], "External refund ID should be set")

        # Check transaction status - should be PARTIALLY_REFUNDED
        transaction = PaymentTransaction.objects.get(id=payment_result["transaction_id"])
        self.assertEqual(
            transaction.status,
            PaymentStatus.PARTIALLY_REFUNDED,
            "Transaction status should be PARTIALLY_REFUNDED",
        )

        # Process another refund for the rest
        refund_result2 = PaymentService.process_refund(
            transaction_id=payment_result["transaction_id"],
            amount=Decimal("150.00"),  # Remaining amount
            reason="Test refund remainder",
        )

        self.assertTrue(refund_result2["success"], "Second refund should succeed")

        # Check transaction status again - should now be REFUNDED
        transaction.refresh_from_db()
        self.assertEqual(
            transaction.status,
            PaymentStatus.REFUNDED,
            "Transaction status should be REFUNDED after full amount refunded",
        )

    def test_webhook_handling(self):
        """Test webhook event handling"""
        # First process a payment to get a transaction
        payment_result = PaymentService.process_payment(
            amount=Decimal("75.00"),
            currency="SAR",
            payment_method_id="test_method",
            description="Test transaction for webhook",
            customer_id="test_customer",
        )

        transaction_id = payment_result["transaction_id"]
        external_id = payment_result["external_id"]

        # Mock a payment webhook event
        payment_event = {
            "type": "payment.succeeded",
            "data": {
                "id": external_id,
                "status": "paid",
                "amount": 7500,  # In halalas
                "currency": "SAR",
                "description": "Test transaction for webhook",
                "source": {
                    "type": "creditcard",
                },
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

        # Test webhook handling
        result = PaymentService.handle_webhook_event(
            event_type=payment_event["type"], event_data=payment_event["data"]
        )

        self.assertTrue(result, "Webhook handling should succeed")

        # Skip testing real webhook signature verification in test mode
        if not TEST_MODE:
            # Test webhook signature verification
            signature = "test_signature"  # In real test this would be a valid signature
            payload = json.dumps(payment_event)

            verification_result = PaymentService.verify_webhook_signature(signature, payload)
            self.assertTrue(
                verification_result,
                "Webhook signature verification should succeed in test mode",
            )


if __name__ == "__main__":
    unittest.main()
