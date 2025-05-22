import uuid
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.authapp.models import User
from apps.bookingapp.models import Appointment

from ..models import PaymentMethod, Refund, Transaction
from ..services.fraud_detector import FraudDetector
from ..services.payment_method_recommender import PaymentMethodRecommender
from ..services.payment_service import PaymentService


class PaymentServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

        self.content_type = ContentType.objects.get_for_model(Appointment)
        self.object_id = uuid.uuid4()

        # Mock appointment for content object
        self.mock_appointment = MagicMock()
        self.mock_appointment.id = self.object_id

        # Mock TransactionManager for isolated testing
        self.transaction_patcher = patch(
            "payment.transaction.TransactionManager.create_transaction"
        )
        self.mock_transaction_manager = self.transaction_patcher.start()

        # Create a mock transaction return value
        self.mock_transaction = MagicMock()
        self.mock_transaction.id = uuid.uuid4()
        self.mock_transaction.moyasar_id = "pay_123456789"
        self.mock_transaction.status = "succeeded"
        self.mock_transaction.metadata = {
            "source": {"transaction_url": "https://test.url"}
        }

        # Configure mock to return our transaction and success
        self.mock_transaction_manager.return_value = (self.mock_transaction, True, None)

    def tearDown(self):
        self.transaction_patcher.stop()

    def test_create_payment(self):
        """Test creating a payment through the service"""
        result = PaymentService.create_payment(
            user_id=self.user.id,
            amount=100.00,
            transaction_type="booking",
            description="Test payment",
            content_object=self.mock_appointment,
            payment_type="card",
        )

        # Check result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["transaction_id"], str(self.mock_transaction.id))
        self.assertEqual(result["status"], self.mock_transaction.status)
        self.assertEqual(result["redirect_url"], "https://test.url")

        # Verify TransactionManager was called with correct parameters
        self.mock_transaction_manager.assert_called_once()
        call_args = self.mock_transaction_manager.call_args[1]
        self.assertEqual(call_args["user"], self.user)
        self.assertEqual(call_args["amount"], 100.00)
        self.assertEqual(call_args["transaction_type"], "booking")
        self.assertEqual(call_args["description"], "Test payment")
        self.assertEqual(call_args["content_object"], self.mock_appointment)
        self.assertEqual(call_args["payment_type"], "card")

    @patch("payment.services.moyasar_service.MoyasarService.process_refund")
    def test_create_refund(self, mock_process_refund):
        """Test creating a refund through the service"""
        # Create a real transaction to refund
        transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            amount_halalas=10000,
            payment_type="card",
            status="succeeded",  # Must be succeeded to refund
            transaction_type="booking",
            content_type=self.content_type,
            object_id=self.object_id,
        )

        # Mock the Moyasar refund response
        mock_process_refund.return_value = {
            "success": True,
            "refund_id": "ref_123456789",
            "data": {"status": "refunded"},
        }

        # Test refunding half the amount
        admin_user = User.objects.create(phone_number="+0987654321", user_type="admin")

        result = PaymentService.create_refund(
            transaction_id=transaction.id,
            amount=50.00,
            reason="Test refund",
            refunded_by_id=admin_user.id,
        )

        # Check result structure
        self.assertTrue(result["success"])
        self.assertIn("refund_id", result)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["amount"], "50.00")

        # Verify refund was created in database
        refund = Refund.objects.get(transaction=transaction)
        self.assertEqual(refund.amount, 50.00)
        self.assertEqual(refund.reason, "Test refund")
        self.assertEqual(refund.status, "succeeded")
        self.assertEqual(refund.refunded_by, admin_user)

        # Verify transaction status was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "partially_refunded")


class PaymentMethodRecommenderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

        # Create payment methods
        self.visa_card = PaymentMethod.objects.create(
            user=self.user,
            type="card",
            token="tok_visa_123",
            last_digits="1234",
            card_brand="visa",
            is_default=True,
        )

        self.mada_card = PaymentMethod.objects.create(
            user=self.user,
            type="mada",
            token="tok_mada_456",
            last_digits="5678",
            is_default=False,
        )

    def test_recommend_payment_method(self):
        """Test payment method recommendation algorithm"""
        # Test with no previous usage
        recommendations = PaymentMethodRecommender.recommend_payment_method(
            self.user, 100.00
        )

        # Should recommend methods in correct order (default first)
        self.assertEqual(len(recommendations), 2)  # Should include all user methods

        # Default method should be first with higher score
        first_rec = recommendations[0]
        self.assertEqual(first_rec["method"], self.visa_card)

        # Test with different amount (large amount)
        recommendations = PaymentMethodRecommender.recommend_payment_method(
            self.user, 2000.00
        )

        # Now card might be preferred for large amounts
        first_rec = recommendations[0]
        self.assertEqual(first_rec["method"], self.visa_card)

        # We'd need more complex tests to check actual scoring behavior
        # which would involve creating transaction history, etc.


class FraudDetectorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

        self.content_type = ContentType.objects.get_for_model(Appointment)

        # Create a normal transaction
        self.normal_transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            amount_halalas=10000,
            payment_type="card",
            status="initiated",
            transaction_type="booking",
            content_type=self.content_type,
            object_id=uuid.uuid4(),
            ip_address="192.168.1.1",
        )

        # Create a high-value transaction (potentially risky)
        self.large_transaction = Transaction.objects.create(
            user=self.user,
            amount=10000.00,  # Very large amount
            amount_halalas=1000000,
            payment_type="card",
            status="initiated",
            transaction_type="booking",
            content_type=self.content_type,
            object_id=uuid.uuid4(),
            ip_address="192.168.1.2",  # Different IP than normal
        )

    def test_assess_fraud_risk(self):
        """Test fraud risk assessment algorithm"""
        # Assess normal transaction
        normal_assessment = FraudDetector.assess_fraud_risk(self.normal_transaction)

        # Check structure
        self.assertIn("risk_score", normal_assessment)
        self.assertIn("risk_level", normal_assessment)
        self.assertIn("flagged_factors", normal_assessment)

        # Normal transaction should be low or medium risk
        self.assertIn(normal_assessment["risk_level"], ["low", "medium"])

        # Assess large transaction
        large_assessment = FraudDetector.assess_fraud_risk(self.large_transaction)

        # Large amount should flag as risky
        self.assertIn("unusual_amount", large_assessment["flagged_factors"])
        self.assertIn("very_large_amount", large_assessment["flagged_factors"])

        # Risk score should be higher
        self.assertGreater(
            large_assessment["risk_score"], normal_assessment["risk_score"]
        )

        # Risk level should be medium or high
        self.assertIn(large_assessment["risk_level"], ["medium", "high"])
