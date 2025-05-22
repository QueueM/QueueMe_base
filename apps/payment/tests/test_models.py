import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.authapp.models import User
from apps.bookingapp.models import Appointment

from ..models import PaymentMethod, Refund, Transaction


class PaymentMethodTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

    def test_payment_method_creation(self):
        """Test creating a payment method"""
        payment_method = PaymentMethod.objects.create(
            user=self.user,
            type="card",
            token="tok_visa_123456",
            last_digits="1234",
            expiry_month="12",
            expiry_year="2025",
            card_brand="visa",
            is_default=True,
        )

        self.assertEqual(payment_method.user, self.user)
        self.assertEqual(payment_method.type, "card")
        self.assertEqual(payment_method.last_digits, "1234")
        self.assertTrue(payment_method.is_default)

        # Test string representation
        self.assertEqual(str(payment_method), "Credit/Debit Card - **** **** **** 1234")

    def test_default_payment_method_behavior(self):
        """Test that only one payment method can be default"""
        # Create first method (default)
        method1 = PaymentMethod.objects.create(
            user=self.user,
            type="card",
            token="tok_visa_111111",
            last_digits="1111",
            is_default=True,
        )

        # Create second method (also marked as default)
        method2 = PaymentMethod.objects.create(
            user=self.user,
            type="mada",
            token="tok_mada_222222",
            last_digits="2222",
            is_default=True,
        )

        # Refresh from database
        method1.refresh_from_db()
        method2.refresh_from_db()

        # First method should no longer be default
        self.assertFalse(method1.is_default)
        self.assertTrue(method2.is_default)


class TransactionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

        self.payment_method = PaymentMethod.objects.create(
            user=self.user,
            type="card",
            token="tok_visa_123456",
            last_digits="1234",
            is_default=True,
        )

        # Mock appointment for transaction object
        self.appointment = type(
            "MockAppointment",
            (),
            {
                "id": uuid.uuid4(),
                "__class__": type(
                    "MockModel",
                    (),
                    {
                        "_meta": type(
                            "MockMeta",
                            (),
                            {"app_label": "bookingapp", "model_name": "appointment"},
                        )
                    },
                ),
            },
        )

        self.content_type = ContentType.objects.get_for_model(Appointment)

    def test_transaction_creation(self):
        """Test creating a transaction"""
        transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            amount_halalas=10000,
            payment_method=self.payment_method,
            payment_type="card",
            status="initiated",
            transaction_type="booking",
            description="Test booking payment",
            content_type=self.content_type,
            object_id=self.appointment.id,
        )

        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.amount, 100.00)
        self.assertEqual(transaction.payment_method, self.payment_method)
        self.assertEqual(transaction.status, "initiated")

        # Test string representation
        self.assertEqual(
            str(transaction), f"{self.user.phone_number} - 100.0 SAR - Initiated"
        )

    def test_automatic_halalas_calculation(self):
        """Test automatic calculation of halalas from amount"""
        # Create without amount_halalas
        transaction = Transaction.objects.create(
            user=self.user,
            amount=99.99,
            payment_type="card",
            status="initiated",
            transaction_type="booking",
            content_type=self.content_type,
            object_id=self.appointment.id,
        )

        # Should automatically calculate amount_halalas
        self.assertEqual(transaction.amount_halalas, 9999)


class RefundTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+1234567890", user_type="customer"
        )

        self.admin = User.objects.create(phone_number="+0987654321", user_type="admin")

        self.content_type = ContentType.objects.get_for_model(Appointment)

        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            amount_halalas=10000,
            payment_type="card",
            status="succeeded",
            transaction_type="booking",
            content_type=self.content_type,
            object_id=uuid.uuid4(),
        )

    def test_refund_creation(self):
        """Test creating a refund"""
        refund = Refund.objects.create(
            transaction=self.transaction,
            amount=50.00,
            amount_halalas=5000,
            reason="Customer requested partial refund",
            status="initiated",
            refunded_by=self.admin,
        )

        self.assertEqual(refund.transaction, self.transaction)
        self.assertEqual(refund.amount, 50.00)
        self.assertEqual(refund.reason, "Customer requested partial refund")
        self.assertEqual(refund.status, "initiated")
        self.assertEqual(refund.refunded_by, self.admin)

        # Test string representation
        self.assertEqual(str(refund), f"{self.transaction} - 50.0 SAR - Initiated")

    def test_automatic_halalas_calculation(self):
        """Test automatic calculation of halalas from amount"""
        refund = Refund.objects.create(
            transaction=self.transaction,
            amount=75.50,
            reason="Test refund",
            status="initiated",
            refunded_by=self.admin,
        )

        # Should automatically calculate amount_halalas
        self.assertEqual(refund.amount_halalas, 7550)
