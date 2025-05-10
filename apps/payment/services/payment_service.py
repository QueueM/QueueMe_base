import logging

from django.db import transaction
from django.utils import timezone

from ..models import PaymentMethod, Refund, Transaction
from ..transaction import TransactionManager

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Service for managing payments and related operations
    """

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
