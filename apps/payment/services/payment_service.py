import json  # Used in other methods
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.payment.models import PaymentStatus, PaymentTransaction
from apps.payment.models import Refund as RefundTransaction
from apps.payment.models import RefundStatus
from apps.payment.moyasar_client import MoyasarClient

from ..models import PaymentMethod, PaymentWalletType, Refund, Transaction
from ..transaction import TransactionManager

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Service for processing payments and managing transactions
    """

    @classmethod
    @transaction.atomic
    def process_payment(
        cls,
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        description: str,
        customer_id: Optional[str] = None,
        company_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        wallet_type: PaymentWalletType = PaymentWalletType.MERCHANT,
        metadata: Optional[Dict[str, Any]] = None,
        callback_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a payment using the specified payment method.

        Args:
            amount: Payment amount as Decimal to ensure precision
            currency: Currency code (e.g., 'SAR')
            payment_method_id: ID of the saved payment method to use or token
            description: Description of the payment
            customer_id: Optional customer ID
            company_id: Optional company ID
            transaction_type: Type of transaction
            wallet_type: Type of wallet to use
            metadata: Optional additional data to store with the transaction
            callback_url: Custom callback URL
            idempotency_key: Optional key to prevent duplicate transactions

        Returns:
            Dictionary with transaction details and status
        """
        try:
            # Validate inputs
            if amount <= Decimal("0"):
                return {
                    "success": False,
                    "message": "Payment amount must be greater than zero",
                }

            # Check for existing transaction with same idempotency key if provided
            if idempotency_key:
                existing_transaction = PaymentTransaction.objects.filter(
                    idempotency_key=idempotency_key,
                    status__in=[PaymentStatus.COMPLETED, PaymentStatus.PENDING],
                ).first()

                if existing_transaction:
                    logger.info(
                        f"Found existing transaction with idempotency key: {idempotency_key}"
                    )
                    return {
                        "success": True,
                        "transaction_id": str(existing_transaction.id),
                        "external_id": existing_transaction.external_id,
                        "status": existing_transaction.status,
                        "amount": float(existing_transaction.amount),
                        "message": "Existing transaction found with provided idempotency key",
                    }

            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = str(uuid.uuid4())

            # Get payment method
            payment_method = None
            source = payment_method_id  # Default to using the ID directly as source

            if not payment_method_id.startswith(("card_", "token_")):
                try:
                    payment_method = PaymentMethod.objects.get(id=payment_method_id)
                    source = payment_method.token
                except ObjectDoesNotExist:
                    return {
                        "success": False,
                        "error_code": "invalid_payment_method",
                        "error_message": "Payment method not found",
                        "status": PaymentStatus.FAILED,
                    }

            # Initialize metadata dictionary if None
            if metadata is None:
                metadata = {}

            # Add transaction type to metadata
            if transaction_type:
                metadata["transaction_type"] = transaction_type

            # Add customer and company IDs to metadata
            if customer_id:
                metadata["customer_id"] = str(customer_id)
            if company_id:
                metadata["company_id"] = str(company_id)

            # Create transaction record (initially pending)
            transaction = PaymentTransaction.objects.create(
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                description=description,
                customer_id=customer_id,
                company_id=company_id,
                metadata=metadata,
                status=PaymentStatus.PENDING,
                wallet_type=wallet_type,
                idempotency_key=idempotency_key,
            )

            # Convert Decimal to integer for payment gateway
            amount_halalas = int(amount * Decimal("100"))

            # Process with payment gateway
            moyasar_client = MoyasarClient(wallet_type=wallet_type)
            gateway_response = moyasar_client.charge(
                amount=amount_halalas,
                currency=currency,
                source=source,
                description=description,
                metadata={"transaction_id": str(transaction.id), **(metadata or {})},
                callback_url=callback_url,
                idempotency_key=idempotency_key,
            )

            # Update transaction based on response
            if gateway_response["success"]:
                transaction.external_id = gateway_response["id"]
                transaction.status = PaymentStatus.COMPLETED
                transaction.gateway_response = gateway_response
                transaction.completed_at = timezone.now()
                transaction.save()

                # Update payment method details if needed
                if (
                    "source" in gateway_response
                    and payment_method.gateway_token
                    != gateway_response["source"].get("id")
                ):
                    payment_method.gateway_token = gateway_response["source"].get("id")
                    payment_method.save()

                return {
                    "success": True,
                    "transaction_id": str(transaction.id),
                    "external_id": transaction.external_id,
                    "status": transaction.status,
                    "amount": float(transaction.amount),
                }
            else:
                transaction.status = PaymentStatus.FAILED
                transaction.gateway_response = gateway_response
                transaction.error_message = gateway_response.get(
                    "message", "Unknown error"
                )
                transaction.save()

                return {
                    "success": False,
                    "transaction_id": str(transaction.id),
                    "message": transaction.error_message,
                }

        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {"success": False, "message": f"Payment processing error: {str(e)}"}

    @classmethod
    @transaction.atomic
    def process_refund(
        cls,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a refund for a transaction.

        Args:
            transaction_id: ID of the transaction to refund
            amount: Optional amount to refund (if partial). If None, full refund.
            reason: Optional reason for the refund
            idempotency_key: Optional key to prevent duplicate refunds

        Returns:
            Dictionary with refund details and status
        """
        try:
            # Check for existing refund with same idempotency key if provided
            if idempotency_key:
                existing_refund = RefundTransaction.objects.filter(
                    idempotency_key=idempotency_key,
                    status__in=[RefundStatus.COMPLETED, RefundStatus.PENDING],
                ).first()

                if existing_refund:
                    logger.info(
                        f"Found existing refund with idempotency key: {idempotency_key}"
                    )
                    return {
                        "success": True,
                        "refund_id": str(existing_refund.id),
                        "external_id": existing_refund.external_id,
                        "status": existing_refund.status,
                        "amount": float(existing_refund.amount),
                        "message": "Existing refund found with provided idempotency key",
                    }

            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = str(uuid.uuid4())

            # Get transaction
            try:
                transaction = PaymentTransaction.objects.get(id=transaction_id)
            except PaymentTransaction.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Transaction not found with ID: {transaction_id}",
                }

            # Check transaction status
            if transaction.status != PaymentStatus.COMPLETED:
                return {
                    "success": False,
                    "message": f"Cannot refund transaction with status: {transaction.status}",
                }

            # Check if already refunded
            existing_refunds = RefundTransaction.objects.filter(
                transaction=transaction, status=RefundStatus.COMPLETED
            )
            total_refunded = sum(Decimal(str(r.amount)) for r in existing_refunds)

            # Default to full remaining amount if not specified
            if amount is None:
                amount = transaction.amount - total_refunded
            else:
                # Ensure amount is a Decimal
                amount = Decimal(str(amount))

            # Validate refund amount
            if amount <= Decimal("0"):
                return {
                    "success": False,
                    "message": "Refund amount must be greater than zero",
                }

            # Check if refund amount exceeds remaining available
            if amount > (transaction.amount - total_refunded):
                return {
                    "success": False,
                    "message": f"Refund amount exceeds available amount. "  # noqa: E501
                    f"Available: {transaction.amount - total_refunded}, Requested: {amount}",
                }

            # Create refund record (initially pending)
            refund = RefundTransaction.objects.create(
                transaction=transaction,
                amount=amount,
                reason=reason,
                status=RefundStatus.PENDING,
                idempotency_key=idempotency_key,
            )

            # Convert Decimal to integer for payment gateway
            amount_halalas = int(amount * Decimal("100"))

            # Process with payment gateway
            moyasar_client = MoyasarClient(wallet_type=transaction.wallet_type)
            gateway_response = moyasar_client.refund(
                payment_id=transaction.external_id,
                amount=amount_halalas,
                reason=reason,
                idempotency_key=idempotency_key,
            )

            # Update refund based on response
            if gateway_response["success"]:
                refund.external_id = gateway_response["id"]
                refund.status = RefundStatus.COMPLETED
                refund.gateway_response = gateway_response
                refund.completed_at = timezone.now()
                refund.save()

                # Update transaction if fully refunded
                if total_refunded + amount >= transaction.amount:
                    transaction.status = PaymentStatus.REFUNDED
                    transaction.save()
                elif total_refunded + amount > Decimal("0"):
                    transaction.status = PaymentStatus.PARTIALLY_REFUNDED
                    transaction.save()

                return {
                    "success": True,
                    "refund_id": str(refund.id),
                    "external_id": refund.external_id,
                    "status": refund.status,
                    "amount": float(refund.amount),
                    "transaction_id": str(transaction.id),
                }
            else:
                refund.status = RefundStatus.FAILED
                refund.gateway_response = gateway_response
                refund.error_message = gateway_response.get("message", "Unknown error")
                refund.save()

                return {
                    "success": False,
                    "refund_id": str(refund.id),
                    "message": refund.error_message,
                }

        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            return {"success": False, "message": f"Refund processing error: {str(e)}"}

    @classmethod
    def get_payment_history(
        cls,
        customer_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get payment history for a customer.

        Args:
            customer_id: ID of the customer
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            limit: Maximum number of transactions to return

        Returns:
            Dictionary with transaction history
        """
        try:
            # Set default date range if not provided
            if not end_date:
                end_date = timezone.now()
            if not start_date:
                start_date = end_date - timedelta(days=90)  # 3 months by default

            # Validate date range
            if end_date < start_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Get transactions for customer
            transactions = PaymentTransaction.objects.filter(
                customer_id=customer_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            ).order_by("-created_at")[:limit]

            # Format transaction data
            formatted_transactions = []
            for transaction in transactions:
                refunds = RefundTransaction.objects.filter(
                    transaction=transaction, status=RefundStatus.COMPLETED
                )
                total_refunded = sum(Decimal(str(r.amount)) for r in refunds)

                formatted_transactions.append(
                    {
                        "id": str(transaction.id),
                        "amount": float(transaction.amount),
                        "currency": transaction.currency,
                        "status": transaction.status,
                        "description": transaction.description,
                        "created_at": transaction.created_at.isoformat(),
                        "completed_at": (
                            transaction.completed_at.isoformat()
                            if transaction.completed_at
                            else None
                        ),
                        "payment_method": (
                            {
                                "id": str(transaction.payment_method.id),
                                "type": transaction.payment_method.payment_type,
                                "last4": transaction.payment_method.last4,
                                "brand": transaction.payment_method.brand,
                            }
                            if transaction.payment_method
                            else None
                        ),
                        "refunded_amount": float(total_refunded),
                        "is_fully_refunded": total_refunded >= transaction.amount,
                        "refunds": [
                            {
                                "id": str(r.id),
                                "amount": float(r.amount),
                                "reason": r.reason,
                                "created_at": r.created_at.isoformat(),
                                "status": r.status,
                            }
                            for r in refunds
                        ],
                    }
                )

            return {
                "success": True,
                "customer_id": customer_id,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "transactions": formatted_transactions,
                "count": len(formatted_transactions),
            }

        except Exception as e:
            logger.error(f"Error getting payment history: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting payment history: {str(e)}",
            }

    @classmethod
    def verify_webhook_signature(cls, signature: str, payload: str) -> bool:
        """
        Verify webhook signature from payment provider.

        Args:
            signature: Signature from the webhook request
            payload: Raw payload from the webhook

        Returns:
            Boolean indicating if signature is valid
        """
        try:
            moyasar_client = MoyasarClient(api_key=settings.MOYASAR_API_KEY)
            return moyasar_client.verify_webhook(signature, payload)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    @classmethod
    @transaction.atomic
    def handle_webhook_event(cls, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Handle webhook events from payment provider.

        Args:
            event_type: Type of event (e.g., 'payment.succeeded')
            event_data: Data from the webhook event

        Returns:
            Boolean indicating success
        """
        try:
            # Handle payment events
            if event_type.startswith("payment."):
                payment_id = event_data.get("id")
                if not payment_id:
                    logger.error("No payment ID in webhook event data")
                    return False

                # Find corresponding transaction
                payment_transaction = PaymentTransaction.objects.filter(
                    external_id=payment_id
                ).first()
                if not payment_transaction:
                    logger.warning(
                        f"No transaction found for external ID: {payment_id}"
                    )
                    return False

                # Update transaction based on event type
                if event_type == "payment.succeeded":
                    if payment_transaction.status != PaymentStatus.COMPLETED:
                        payment_transaction.status = PaymentStatus.COMPLETED
                        payment_transaction.completed_at = timezone.now()
                        payment_transaction.gateway_response = event_data
                        payment_transaction.save()
                        logger.info(
                            f"Transaction {payment_transaction.id} marked as completed from webhook"
                        )

                elif event_type == "payment.failed":
                    if payment_transaction.status != PaymentStatus.FAILED:
                        payment_transaction.status = PaymentStatus.FAILED
                        payment_transaction.gateway_response = event_data
                        payment_transaction.error_message = event_data.get(
                            "message", "Payment failed"
                        )
                        payment_transaction.save()
                        logger.info(
                            f"Transaction {payment_transaction.id} marked as failed from webhook"
                        )

                # Handle other payment event types as needed

            # Handle refund events
            elif event_type.startswith("refund."):
                refund_id = event_data.get("id")
                if not refund_id:
                    logger.error("No refund ID in webhook event data")
                    return False

                # Find corresponding refund
                refund = RefundTransaction.objects.filter(external_id=refund_id).first()
                if not refund:
                    logger.warning(f"No refund found for external ID: {refund_id}")
                    return False

                # Update refund based on event type
                if event_type == "refund.succeeded":
                    if refund.status != RefundStatus.COMPLETED:
                        refund.status = RefundStatus.COMPLETED
                        refund.completed_at = timezone.now()
                        refund.gateway_response = event_data
                        refund.save()

                        # Update parent transaction
                        transaction = refund.transaction
                        existing_refunds = RefundTransaction.objects.filter(
                            transaction=transaction, status=RefundStatus.COMPLETED
                        )
                        total_refunded = sum(
                            Decimal(str(r.amount)) for r in existing_refunds
                        )

                        if total_refunded >= transaction.amount:
                            transaction.status = PaymentStatus.REFUNDED
                            transaction.save()
                        elif total_refunded > Decimal("0"):
                            transaction.status = PaymentStatus.PARTIALLY_REFUNDED
                            transaction.save()

                        logger.info(
                            f"Refund {refund.id} marked as completed from webhook"
                        )

                elif event_type == "refund.failed":
                    if refund.status != RefundStatus.FAILED:
                        refund.status = RefundStatus.FAILED
                        refund.gateway_response = event_data
                        refund.error_message = event_data.get(
                            "message", "Refund failed"
                        )
                        refund.save()
                        logger.info(f"Refund {refund.id} marked as failed from webhook")

                # Handle other refund event types as needed

            return True

        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def create_payment(
        user_id,
        amount,
        transaction_type,
        description,
        content_object,
        payment_method_id=None,
        payment_type=None,
    ):
        """
        Create a payment transaction

        Args:
            user_id: User ID
            amount: Payment amount
            transaction_type: Type of transaction
            description: Payment description
            content_object: Related object (booking, subscription, etc.)
            payment_method_id: Optional saved payment method ID
            payment_type: Payment type if not using saved method

        Returns:
            dict: Result with transaction info and status
        """
        from apps.authapp.models import User

        user = User.objects.get(id=user_id)

        # Get payment method if provided
        payment_method = None
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id, user=user
                )
            except PaymentMethod.DoesNotExist:
                return {"success": False, "error": "Payment method not found"}

        # Call transaction manager to create the transaction
        transaction_obj, success, error_msg = TransactionManager.create_transaction(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            content_object=content_object,
            payment_method=payment_method,
            payment_type=payment_type,
        )

        if not success:
            return {
                "success": False,
                "error": error_msg,
                "transaction_id": str(transaction_obj.id) if transaction_obj else None,
            }

        # Prepare response
        result = {
            "success": True,
            "transaction_id": str(transaction_obj.id),
            "moyasar_id": transaction_obj.moyasar_id,
            "status": transaction_obj.status,
        }

        # Add redirect URL if provided in Moyasar response
        if transaction_obj.metadata and "source" in transaction_obj.metadata:
            source_data = transaction_obj.metadata["source"]
            if "transaction_url" in source_data:
                result["redirect_url"] = source_data["transaction_url"]

        return result

    @staticmethod
    @transaction.atomic
    def handle_payment_webhook(webhook_data):
        """
        Handle payment webhook from Moyasar

        Args:
            webhook_data: Webhook payload from Moyasar

        Returns:
            bool: Success status
        """
        moyasar_id = webhook_data.get("id")

        if not moyasar_id:
            logger.error("Missing Moyasar ID in webhook data")
            return False

        try:
            # Find transaction by Moyasar ID
            transaction = Transaction.objects.get(moyasar_id=moyasar_id)

            # Update transaction status based on webhook status
            status = webhook_data.get("status")

            if status == "paid":
                transaction.status = "succeeded"
            elif status == "failed":
                transaction.status = "failed"
                transaction.failure_message = webhook_data.get("message")
                transaction.failure_code = webhook_data.get("type")

            # Update metadata
            transaction.metadata.update(webhook_data)
            transaction.save()

            # If payment succeeded, update related object
            if transaction.status == "succeeded":
                PaymentService.handle_successful_payment(transaction)

            return True

        except Transaction.DoesNotExist:
            logger.error(f"Transaction with Moyasar ID {moyasar_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return False

    @staticmethod
    def handle_successful_payment(transaction):
        """
        Update related object after successful payment

        Args:
            transaction: Transaction that succeeded

        Returns:
            bool: Success status
        """
        # This function updates the status of the content object
        # based on the transaction type
        try:
            if transaction.transaction_type == "booking":
                # Update appointment payment status
                appointment = transaction.content_object
                appointment.payment_status = "paid"
                appointment.transaction_id = str(transaction.id)
                appointment.save()

                # Send confirmation notification
                from apps.notificationsapp.services.notification_service import (
                    NotificationService,
                )

                NotificationService.send_notification(
                    user_id=transaction.user.id,
                    notification_type="payment_confirmation",
                    data={
                        "appointment_id": str(appointment.id),
                        "service_name": appointment.service.name,
                        "amount": str(transaction.amount),
                        "date": appointment.start_time.strftime("%d %b, %Y"),
                        "time": appointment.start_time.strftime("%I:%M %p"),
                    },
                )

            elif transaction.transaction_type == "subscription":
                # Update subscription status
                subscription = transaction.content_object
                subscription.status = "active"
                subscription.current_period_end = timezone.now() + timezone.timedelta(
                    days=30
                )  # Assuming monthly
                subscription.save()

                # Send confirmation notification
                from apps.notificationsapp.services.notification_service import (
                    NotificationService,
                )

                NotificationService.send_notification(
                    user_id=transaction.user.id,
                    notification_type="payment_confirmation",
                    data={
                        "subscription_id": str(subscription.id),
                        "plan_name": subscription.plan.name,
                        "amount": str(transaction.amount),
                        "period_end": subscription.current_period_end.strftime(
                            "%d %b, %Y"
                        ),
                    },
                )

            elif transaction.transaction_type == "ad":
                # Update ad status
                ad = transaction.content_object
                ad.status = "active"
                ad.save()

                # Send confirmation notification
                from apps.notificationsapp.services.notification_service import (
                    NotificationService,
                )

                NotificationService.send_notification(
                    user_id=transaction.user.id,
                    notification_type="payment_confirmation",
                    data={
                        "ad_id": str(ad.id),
                        "ad_name": ad.name,
                        "amount": str(transaction.amount),
                    },
                )

            return True

        except Exception as e:
            logger.error(f"Error handling successful payment: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def create_refund(transaction_id, amount, reason, refunded_by_id):
        """
        Create a refund for a transaction

        Args:
            transaction_id: Transaction ID
            amount: Refund amount
            reason: Refund reason
            refunded_by_id: User ID of person issuing refund

        Returns:
            dict: Result with refund info and status
        """
        try:
            from apps.authapp.models import User

            transaction = Transaction.objects.get(id=transaction_id)
            refunded_by = User.objects.get(id=refunded_by_id)

            # Check if transaction can be refunded
            if transaction.status != "succeeded":
                return {
                    "success": False,
                    "error": "Only succeeded transactions can be refunded",
                }

            # Convert amount to halalas
            amount_halalas = int(amount * 100)

            # Create refund record
            refund = Refund.objects.create(
                transaction=transaction,
                amount=amount,
                amount_halalas=amount_halalas,
                reason=reason,
                refunded_by=refunded_by,
            )

            # Process refund with Moyasar
            from .moyasar_service import MoyasarService

            result = MoyasarService.process_refund(refund)

            if result.get("success"):
                # Update refund with Moyasar ID
                refund.moyasar_id = result.get("refund_id")
                refund.status = "succeeded"
                refund.save()

                # Update transaction status
                total_refunded = sum(
                    r.amount for r in transaction.refunds.filter(status="succeeded")
                )

                if total_refunded >= transaction.amount:
                    transaction.status = "refunded"
                else:
                    transaction.status = "partially_refunded"

                transaction.save()

                # If refund succeeded and it's a booking, update the appointment status
                if transaction.transaction_type == "booking":
                    appointment = transaction.content_object
                    appointment.status = "cancelled"
                    appointment.cancellation_reason = reason
                    appointment.save()

                return {
                    "success": True,
                    "refund_id": str(refund.id),
                    "status": refund.status,
                    "amount": str(refund.amount),
                }
            else:
                # Update refund with error
                refund.status = "failed"
                refund.failure_message = result.get("error")
                refund.save()

                return {
                    "success": False,
                    "refund_id": str(refund.id),
                    "error": result.get("error"),
                }

        except Transaction.DoesNotExist:
            return {"success": False, "error": "Transaction not found"}
        except User.DoesNotExist:
            return {"success": False, "error": "User not found"}
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def add_payment_method(user_id, token, payment_type, make_default=False):
        """
        Add a saved payment method for user

        Args:
            user_id: User ID
            token: Payment method token from Moyasar
            payment_type: Type of payment method
            make_default: Whether to make this the default method

        Returns:
            dict: Result with payment method info and status
        """
        try:
            from apps.authapp.models import User

            user = User.objects.get(id=user_id)

            # Extract card details from token (simplified)
            # In production, you would call Moyasar API to get details
            card_info = {}
            if payment_type == "card":
                # This is simplified - in reality you'd parse this from Moyasar
                # Or make an API call to get the details
                if "-" in token:
                    parts = token.split("-")
                    if len(parts) > 1:
                        card_info = {
                            "last_digits": parts[-1][-4:],
                            "expiry_month": "12",  # Placeholder
                            "expiry_year": "2025",  # Placeholder
                            "card_brand": "visa",  # Placeholder
                        }

            # Create payment method
            payment_method = PaymentMethod(
                user=user, type=payment_type, token=token, is_default=make_default
            )

            # Add card details if available
            if card_info:
                payment_method.last_digits = card_info.get("last_digits")
                payment_method.expiry_month = card_info.get("expiry_month")
                payment_method.expiry_year = card_info.get("expiry_year")
                payment_method.card_brand = card_info.get("card_brand")

            payment_method.save()

            return {
                "success": True,
                "payment_method_id": str(payment_method.id),
                "type": payment_method.type,
                "is_default": payment_method.is_default,
            }

        except User.DoesNotExist:
            return {"success": False, "error": "User not found"}
        except Exception as e:
            logger.error(f"Error adding payment method: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def set_default_payment_method(user_id, payment_method_id):
        """
        Set a payment method as default

        Args:
            user_id: User ID
            payment_method_id: Payment method ID

        Returns:
            dict: Result with status
        """
        try:
            payment_method = PaymentMethod.objects.get(
                id=payment_method_id, user_id=user_id
            )

            # Set as default
            payment_method.is_default = True
            payment_method.save()  # This will handle removing default from others

            return {"success": True}

        except PaymentMethod.DoesNotExist:
            return {"success": False, "error": "Payment method not found"}
        except Exception as e:
            logger.error(f"Error setting default payment method: {str(e)}")
            return {"success": False, "error": str(e)}
