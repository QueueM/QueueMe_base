import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand
from payment.models import Transaction
from payment.services.payment_service import PaymentService

from apps.authapp.models import User
from apps.bookingapp.models import Appointment


class Command(BaseCommand):
    help = "Test payment processing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode", type=str, choices=["create", "refund", "check"], default="create"
        )
        parser.add_argument("--user_id", type=str, required=False, help="User ID")
        parser.add_argument(
            "--transaction_id",
            type=str,
            required=False,
            help="Transaction ID for refunds or checks",
        )
        parser.add_argument(
            "--amount", type=float, required=False, default=100.0, help="Amount in SAR"
        )

    def handle(self, *args, **options):
        mode = options["mode"]

        if mode == "create":
            self._create_test_payment(options)
        elif mode == "refund":
            self._create_test_refund(options)
        elif mode == "check":
            self._check_transaction_status(options)

    def _create_test_payment(self, options):
        # Get user
        user_id = options.get("user_id")
        if not user_id:
            user = User.objects.filter(user_type="customer").first()
            if not user:
                self.stdout.write(self.style.ERROR("No customer users found"))
                return
        else:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
                return

        # Get an appointment to pay for, or create a fake one
        appointment = Appointment.objects.filter(user=user, payment_status="pending").first()
        if not appointment:
            # This is just a placeholder, it won't be saved to DB
            from django.contrib.contenttypes.models import ContentType

            # unused_unused_ct = ContentType.objects.get_for_model(Appointment)

            self.stdout.write(
                self.style.WARNING(
                    "No pending appointments found, creating a test transaction only"
                )
            )
            # The transaction will be created but not linked to a real appointment
            content_object = type("MockAppointment", (), {"id": uuid.uuid4()})
        else:
            content_object = appointment

        # Create payment
        amount = Decimal(str(options.get("amount", 100.0)))
        result = PaymentService.create_payment(
            user_id=user.id,
            amount=amount,
            transaction_type="booking",
            description="Test payment",
            content_object=content_object,
            payment_type="card",  # Default to card for testing
        )

        if result["success"]:
            self.stdout.write(
                self.style.SUCCESS(f'Created test payment: {result["transaction_id"]}')
            )
            self.stdout.write(f'Status: {result["status"]}')
            if "redirect_url" in result:
                self.stdout.write(f'Redirect URL: {result["redirect_url"]}')
        else:
            self.stdout.write(self.style.ERROR(f'Failed to create payment: {result["error"]}'))

    def _create_test_refund(self, options):
        transaction_id = options.get("transaction_id")
        if not transaction_id:
            self.stdout.write(self.style.ERROR("Transaction ID is required for refunds"))
            return

        # Get an admin user for refunding
        admin_user = User.objects.filter(user_type="admin").first()
        if not admin_user:
            self.stdout.write(self.style.ERROR("No admin users found to process refund"))
            return

        # Get amount or use half of the transaction amount
        try:
            transaction = Transaction.objects.get(id=transaction_id)
            amount = Decimal(str(options.get("amount", transaction.amount / 2)))

            # Create refund
            result = PaymentService.create_refund(
                transaction_id=transaction_id,
                amount=amount,
                reason="Test refund",
                refunded_by_id=admin_user.id,
            )

            if result["success"]:
                self.stdout.write(self.style.SUCCESS(f'Created test refund: {result["refund_id"]}'))
                self.stdout.write(f'Status: {result["status"]}')
                self.stdout.write(f'Amount: {result["amount"]}')
            else:
                self.stdout.write(self.style.ERROR(f'Failed to create refund: {result["error"]}'))

        except Transaction.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Transaction with ID {transaction_id} not found"))

    def _check_transaction_status(self, options):
        transaction_id = options.get("transaction_id")
        if not transaction_id:
            self.stdout.write(self.style.ERROR("Transaction ID is required for status check"))
            return

        try:
            transaction = Transaction.objects.get(id=transaction_id)
            self.stdout.write(self.style.SUCCESS(f"Transaction {transaction_id}:"))
            self.stdout.write(f"Status: {transaction.status}")
            self.stdout.write(f"Amount: {transaction.amount} SAR")
            self.stdout.write(f"Created: {transaction.created_at}")

            if transaction.moyasar_id:
                self.stdout.write(f"Moyasar ID: {transaction.moyasar_id}")

            if transaction.status == "failed":
                self.stdout.write(
                    self.style.WARNING(f"Failure reason: {transaction.failure_message}")
                )

        except Transaction.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Transaction with ID {transaction_id} not found"))
