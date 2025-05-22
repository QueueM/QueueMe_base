import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction as db_transaction

from .models import Transaction
from .services.moyasar_service import MoyasarService

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages payment transactions with atomicity and reliability
    """

    @staticmethod
    @db_transaction.atomic
    def create_transaction(
        user,
        amount,
        transaction_type,
        description,
        content_object,
        payment_method=None,
        payment_type=None,
        metadata=None,
    ):
        """
        Creates a new transaction record and initiates payment processing

        Args:
            user: User making the payment
            amount: Decimal amount in SAR
            transaction_type: Type of transaction (booking, subscription, ad)
            description: Transaction description
            content_object: Object being paid for
            payment_method: Optional PaymentMethod object (saved method)
            payment_type: Payment type if no saved method is used
            metadata: Additional metadata to store

        Returns:
            tuple: (transaction, success, error_msg)
        """
        if not payment_method and not payment_type:
            return None, False, "Either payment method or payment type is required"

        # Calculate amount in halalas
        amount_halalas = int(amount * 100)

        # Get content type
        content_type = ContentType.objects.get_for_model(content_object)

        # Determine payment_type from method if not provided
        if payment_method and not payment_type:
            payment_type = payment_method.type

        # Create transaction record
        transaction = Transaction.objects.create(
            amount=amount,
            amount_halalas=amount_halalas,
            user=user,
            payment_method=payment_method,
            payment_type=payment_type,
            transaction_type=transaction_type,
            description=description,
            content_type=content_type,
            object_id=content_object.id,
            metadata=metadata or {},
            status="initiated",
        )

        logger.info(
            f"Created transaction {transaction.id} for {user.phone_number}, amount: {amount} SAR, type: {transaction_type}"
        )

        try:
            # Get appropriate callback URL based on transaction type
            wallet_config = MoyasarService.get_wallet_config(transaction_type)
            callback_url = f"/api/payments/callback/{transaction.id}/"

            # Process with Moyasar using the correct wallet
            moyasar_response = MoyasarService.create_payment(
                transaction=transaction,
                callback_url=callback_url,
            )

            # Update transaction with Moyasar ID
            if moyasar_response.get("id"):
                transaction.moyasar_id = moyasar_response["id"]

                # Update status based on Moyasar response
                if moyasar_response.get("status") == "initiated":
                    transaction.status = "initiated"
                elif moyasar_response.get("status") == "paid":
                    transaction.status = "succeeded"

                # Store wallet ID in metadata
                transaction.metadata["wallet_id"] = wallet_config.get("wallet_id", "")
                transaction.metadata.update(moyasar_response)
                transaction.save()

                return transaction, True, None
            else:
                # Handle error
                transaction.status = "failed"
                transaction.failure_message = moyasar_response.get(
                    "message", "Unknown error"
                )
                transaction.failure_code = moyasar_response.get("type", "unknown")
                transaction.save()

                return transaction, False, transaction.failure_message

        except Exception as e:
            logger.error(
                f"Error creating payment for transaction {transaction.id}: {str(e)}"
            )

            # Update transaction with error
            transaction.status = "failed"
            transaction.failure_message = str(e)
            transaction.save()

            return transaction, False, str(e)

    @staticmethod
    @db_transaction.atomic
    def update_transaction_status(transaction_id, moyasar_data):
        """
        Updates transaction status based on webhook data from Moyasar

        Args:
            transaction_id: Transaction UUID
            moyasar_data: Data from Moyasar webhook

        Returns:
            bool: Success status
        """
        try:
            transaction = Transaction.objects.get(id=transaction_id)

            # Update status based on Moyasar status
            status = moyasar_data.get("status")
            if status == "paid":
                transaction.status = "succeeded"
            elif status == "failed":
                transaction.status = "failed"
                transaction.failure_message = moyasar_data.get("message")
                transaction.failure_code = moyasar_data.get("type")

            # Update metadata
            transaction.metadata.update(moyasar_data)
            transaction.save()

            logger.info(
                f"Updated transaction {transaction_id} status to {transaction.status} for type {transaction.transaction_type}"
            )
            return True

        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found for update")
            return False
        except Exception as e:
            logger.error(f"Error updating transaction {transaction_id}: {str(e)}")
            return False
