"""
Moyasar payment service for handling multiple payment wallet integration.

This module provides a comprehensive service for interacting with the Moyasar payment gateway,
supporting multiple wallet types (subscription, ads, merchant) with proper error handling,
retry mechanisms, and webhook processing.
"""

import hashlib
import hmac
import logging
import time
import uuid
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Union

import requests
from django.conf import settings
from django.utils import timezone

from apps.payment.models import PaymentMethod, PaymentWalletType, Transaction

# Configure logging
logger = logging.getLogger(__name__)

# Constants for retry mechanism
MAX_VERIFICATION_RETRIES = 3
VERIFICATION_RETRY_DELAY = 2.0  # seconds


class MoyasarService:
    """
    Service for making requests to Moyasar payment gateway with support
    for multiple wallet types (subscription, ads, merchant).

    This service handles:
    - Payment creation and processing
    - Payment verification and status updates
    - Webhook signature verification and event processing
    - Error handling and retry mechanisms
    - Transaction idempotency

    Each wallet type (subscription, ads, merchant) has its own API key and
    webhook secret, allowing for separate payment flows and accounting.
    """

    ENDPOINT = "https://api.moyasar.com/v1"

    class PaymentStatus(str, Enum):
        """
        Enum representing payment status values from Moyasar.

        These status values are returned by the Moyasar API and mapped to
        our internal transaction status values.
        """

        INITIATED = "initiated"
        PAID = "paid"
        FAILED = "failed"
        AUTHORIZED = "authorized"
        CAPTURED = "captured"
        REFUNDED = "refunded"
        VOIDED = "voided"

    @classmethod
    def get_wallet_config(cls, wallet_type: str) -> Dict[str, str]:
        """
        Get the configuration for a specific wallet.

        Args:
            wallet_type: The wallet type to get configuration for
                (subscription, ads, merchant)

        Returns:
            Dictionary with wallet configuration including API key and webhook secret

        Raises:
            ValueError: If the wallet type is not supported
        """
        if wallet_type not in PaymentWalletType.values:
            raise ValueError(f"Unsupported wallet type: {wallet_type}")

        return {
            "api_key": settings.MOYASAR_API_KEYS.get(wallet_type),
            "webhook_secret": settings.MOYASAR_WEBHOOK_SECRETS.get(wallet_type),
        }

    @classmethod
    def create_payment(
        cls,
        amount: Union[int, float, Decimal],
        payment_type: str,
        entity_type: str,
        entity_id: str,
        user_id: str,
        description: str,
        payment_method: str,
        wallet_type: str,
        callback_url: str,
        card_data: Optional[Dict[str, str]] = None,
        saved_card_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a payment through Moyasar payment gateway.

        This method handles both new card payments and payments with saved cards.
        It also supports idempotency to prevent duplicate payments.

        Args:
            amount: Payment amount in SAR
            payment_type: Type of payment (booking, subscription, advertisement)
            entity_type: Type of entity being paid for (appointment, subscription_plan, ad_campaign)
            entity_id: ID of the entity being paid for
            user_id: ID of the user making the payment
            description: Payment description
            payment_method: Method of payment (creditcard, applepay, stcpay, saved_card)
            wallet_type: Type of wallet to use (subscription, ads, merchant)
            callback_url: URL to redirect after payment
            card_data: Card data for new card payments (optional)
            saved_card_id: ID of saved payment method for saved card payments (optional)
            idempotency_key: Key for ensuring idempotency (optional)

        Returns:
            Dictionary with payment result including transaction_id and status

        Raises:
            ValueError: If payment creation fails
            ConnectionError: If there's a network issue
        """
        # Check for existing transaction with same idempotency key
        if idempotency_key:
            existing_transaction = Transaction.objects.filter(
                idempotency_key=idempotency_key
            ).first()

            if existing_transaction:
                logger.info(
                    f"Found existing transaction with idempotency key {idempotency_key}: "
                    f"{existing_transaction.transaction_id}"
                )
                return {
                    "transaction_id": existing_transaction.transaction_id,
                    "status": existing_transaction.status,
                }

        # Convert amount to halalas (Moyasar uses smallest currency unit)
        amount_halalas = int(Decimal(amount) * 100)

        # Get wallet configuration
        wallet_config = cls.get_wallet_config(wallet_type)
        api_key = wallet_config["api_key"]

        # Prepare payment data
        payment_data = {
            "amount": amount_halalas,
            "currency": "SAR",
            "description": description,
            "callback_url": callback_url,
        }

        # Handle different payment methods
        if payment_method == "saved_card" and saved_card_id:
            # Get saved card details
            try:
                payment_method_obj = PaymentMethod.objects.get(id=saved_card_id)
                payment_data["source"] = {
                    "type": "creditcard",
                    "token": payment_method_obj.token,
                }
            except PaymentMethod.DoesNotExist:
                raise ValueError(f"Payment method with ID {saved_card_id} not found")
        elif payment_method == "creditcard" and card_data:
            payment_data["source"] = {
                "type": "creditcard",
                "token": card_data.get("token"),
            }
        elif payment_method == "applepay" and card_data:
            payment_data["source"] = {
                "type": "applepay",
                "token": card_data.get("token"),
            }
        elif payment_method == "stcpay":
            payment_data["source"] = {
                "type": "stcpay",
                "mobile_number": card_data.get("mobile_number") if card_data else None,
            }
        else:
            raise ValueError(f"Invalid payment method or missing required data")

        # Generate transaction ID
        transaction_id = f"txn_{uuid.uuid4().hex[:16]}"

        # Create transaction record
        transaction = Transaction.objects.create(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            status=cls.PaymentStatus.INITIATED,
            entity_type=entity_type,
            entity_id=entity_id,
            payment_type=payment_type,
            wallet_type=wallet_type,
            provider="moyasar",
            idempotency_key=idempotency_key,
        )

        # Add metadata to payment
        payment_data["metadata"] = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payment_type": payment_type,
            "wallet_type": wallet_type,
        }

        # Add idempotency key to headers if provided
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        # Make request to Moyasar
        try:
            logger.info(f"Creating payment with Moyasar: {payment_data}")
            response = requests.post(
                f"{cls.ENDPOINT}/payments",
                json=payment_data,
                auth=(api_key, ""),
                headers=headers,
            )

            if response.status_code != 200:
                error_message = f"Failed to create payment: {response.text}"
                logger.error(error_message)
                transaction.status = "failed"
                transaction.error_message = error_message
                transaction.save()
                raise ValueError(error_message)

            # Parse response
            payment_response = response.json()
            moyasar_id = payment_response.get("id")

            # Update transaction with Moyasar ID
            transaction.provider_transaction_id = moyasar_id
            transaction.save()

            logger.info(f"Payment created successfully: {moyasar_id}")

            return {
                "transaction_id": transaction_id,
                "moyasar_id": moyasar_id,
                "status": transaction.status,
            }

        except requests.RequestException as e:
            error_message = f"Network error creating payment: {str(e)}"
            logger.error(error_message)
            transaction.status = "failed"
            transaction.error_message = error_message
            transaction.save()
            raise ConnectionError(error_message)

    @classmethod
    def verify_payment(cls, transaction_id: str) -> Dict[str, Any]:
        """
        Verify payment status with Moyasar.

        Args:
            transaction_id: ID of the transaction to verify

        Returns:
            Dictionary with verification result including status

        Raises:
            ValueError: If payment verification fails
            ConnectionError: If there's a network issue
        """
        # Get transaction
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            raise ValueError(f"Transaction with ID {transaction_id} not found")

        # Get wallet configuration
        wallet_config = cls.get_wallet_config(transaction.wallet_type)
        api_key = wallet_config["api_key"]

        # Get Moyasar payment ID
        moyasar_id = transaction.provider_transaction_id
        if not moyasar_id:
            raise ValueError(f"Transaction {transaction_id} has no Moyasar ID")

        # Make request to Moyasar
        try:
            logger.info(f"Verifying payment with Moyasar: {moyasar_id}")
            response = requests.get(
                f"{cls.ENDPOINT}/payments/{moyasar_id}", auth=(api_key, "")
            )

            if response.status_code != 200:
                error_message = f"Failed to verify payment: {response.text}"
                logger.error(error_message)
                raise ValueError(error_message)

            # Parse response
            payment_response = response.json()
            moyasar_status = payment_response.get("status")

            # Map Moyasar status to our status
            status_mapping = {
                cls.PaymentStatus.PAID: "succeeded",
                cls.PaymentStatus.CAPTURED: "succeeded",
                cls.PaymentStatus.FAILED: "failed",
                cls.PaymentStatus.AUTHORIZED: "authorized",
                cls.PaymentStatus.REFUNDED: "refunded",
                cls.PaymentStatus.VOIDED: "cancelled",
            }

            new_status = status_mapping.get(moyasar_status, transaction.status)

            # Update transaction status if changed
            if new_status != transaction.status:
                transaction.status = new_status
                transaction.last_verified_at = timezone.now()
                transaction.save()

                logger.info(
                    f"Updated transaction {transaction_id} status to {new_status}"
                )

            return {
                "transaction_id": transaction_id,
                "moyasar_id": moyasar_id,
                "status": new_status,
                "amount": transaction.amount,
            }

        except requests.RequestException as e:
            error_message = f"Network error verifying payment: {str(e)}"
            logger.error(error_message)
            raise ConnectionError(error_message)

    @classmethod
    def verify_payment_with_retry(cls, transaction_id: str) -> Dict[str, Any]:
        """
        Verify payment status with retry mechanism for transient errors.

        This method will retry verification up to MAX_VERIFICATION_RETRIES times
        with exponential backoff between retries.

        Args:
            transaction_id: ID of the transaction to verify

        Returns:
            Dictionary with verification result including status

        Raises:
            ValueError: If payment verification fails after all retries
        """
        last_error = None

        for attempt in range(MAX_VERIFICATION_RETRIES):
            try:
                return cls.verify_payment(transaction_id)
            except ConnectionError as e:
                # Network errors are retryable
                last_error = e
                logger.warning(
                    f"Verification attempt {attempt + 1}/{MAX_VERIFICATION_RETRIES} "
                    f"failed with network error: {str(e)}"
                )
                # Wait before retry with exponential backoff
                time.sleep(VERIFICATION_RETRY_DELAY * (2**attempt))
            except ValueError as e:
                # API errors might be retryable if they're server errors
                if "500" in str(e) or "503" in str(e) or "timeout" in str(e).lower():
                    last_error = e
                    logger.warning(
                        f"Verification attempt {attempt + 1}/{MAX_VERIFICATION_RETRIES} "
                        f"failed with server error: {str(e)}"
                    )
                    # Wait before retry with exponential backoff
                    time.sleep(VERIFICATION_RETRY_DELAY * (2**attempt))
                else:
                    # Client errors are not retryable
                    raise

        # If we get here, all retries failed
        error_message = (
            f"Payment verification failed after {MAX_VERIFICATION_RETRIES} attempts"
        )
        if last_error:
            error_message += f": {str(last_error)}"

        logger.error(error_message)
        raise ValueError(error_message)

    @classmethod
    def refund_payment(
        cls,
        transaction_id: str,
        amount: Optional[Union[int, float, Decimal]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refund a payment through Moyasar.

        Args:
            transaction_id: ID of the transaction to refund
            amount: Amount to refund (optional, defaults to full amount)
            reason: Reason for refund (optional)

        Returns:
            Dictionary with refund result

        Raises:
            ValueError: If refund fails
            ConnectionError: If there's a network issue
        """
        # Get transaction
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            raise ValueError(f"Transaction with ID {transaction_id} not found")

        # Check if transaction can be refunded
        if transaction.status not in ["succeeded", "authorized", "captured"]:
            raise ValueError(
                f"Transaction {transaction_id} cannot be refunded (status: {transaction.status})"
            )

        # Get wallet configuration
        wallet_config = cls.get_wallet_config(transaction.wallet_type)
        api_key = wallet_config["api_key"]

        # Get Moyasar payment ID
        moyasar_id = transaction.provider_transaction_id
        if not moyasar_id:
            raise ValueError(f"Transaction {transaction_id} has no Moyasar ID")

        # Prepare refund data
        refund_data = {}
        if amount is not None:
            # Convert amount to halalas
            refund_data["amount"] = int(Decimal(amount) * 100)

        if reason:
            refund_data["reason"] = reason

        # Make request to Moyasar
        try:
            logger.info(f"Refunding payment with Moyasar: {moyasar_id}")
            response = requests.post(
                f"{cls.ENDPOINT}/payments/{moyasar_id}/refund",
                json=refund_data,
                auth=(api_key, ""),
            )

            if response.status_code != 200:
                error_message = f"Failed to refund payment: {response.text}"
                logger.error(error_message)
                raise ValueError(error_message)

            # Parse response
            refund_response = response.json()
            refund_id = (
                refund_response.get("refunds", [{}])[0].get("id")
                if refund_response.get("refunds")
                else None
            )

            # Update transaction status
            transaction.status = "refunded"
            transaction.refund_id = refund_id
            transaction.refund_amount = (
                amount if amount is not None else transaction.amount
            )
            transaction.refund_reason = reason
            transaction.refunded_at = timezone.now()
            transaction.save()

            logger.info(f"Payment refunded successfully: {refund_id}")

            return {
                "transaction_id": transaction_id,
                "moyasar_id": moyasar_id,
                "refund_id": refund_id,
                "status": "refunded",
                "amount": amount if amount is not None else transaction.amount,
            }

        except requests.RequestException as e:
            error_message = f"Network error refunding payment: {str(e)}"
            logger.error(error_message)
            raise ConnectionError(error_message)

    @classmethod
    def verify_webhook_signature(
        cls, payload: bytes, signature: str, wallet_type: str
    ) -> bool:
        """
        Verify the signature of a webhook from Moyasar.

        Args:
            payload: Raw request body as bytes
            signature: Signature from the request header
            wallet_type: Type of wallet (subscription, ads, merchant)

        Returns:
            True if signature is valid, False otherwise
        """
        if not signature:
            logger.warning("Missing webhook signature")
            return False

        # Get webhook secret for wallet type
        wallet_config = cls.get_wallet_config(wallet_type)
        webhook_secret = wallet_config["webhook_secret"]

        if not webhook_secret:
            logger.warning(
                f"No webhook secret configured for wallet type: {wallet_type}"
            )
            return False

        # Compute expected signature
        expected_signature = hmac.new(
            webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        # Compare signatures
        is_valid = hmac.compare_digest(expected_signature, signature)

        if not is_valid:
            logger.warning(f"Invalid webhook signature for wallet type: {wallet_type}")

        return is_valid

    @classmethod
    def process_webhook(
        cls, payload: Dict[str, Any], headers: Dict[str, str], wallet_type: str
    ) -> Dict[str, Any]:
        """
        Process a webhook from Moyasar.

        Args:
            payload: Webhook payload
            headers: Request headers
            wallet_type: Type of wallet (subscription, ads, merchant)

        Returns:
            Dictionary with processing result

        Raises:
            ValueError: If webhook processing fails
        """
        # Get event type and data
        event_type = payload.get("type")
        event_data = payload.get("data", {})

        if not event_type or not event_data:
            raise ValueError("Invalid webhook payload")

        logger.info(f"Processing {wallet_type} webhook: {event_type}")

        # Map event types to transaction statuses
        status_mapping = {
            "payment.paid": "succeeded",
            "payment.failed": "failed",
            "payment.refunded": "refunded",
            "payment.captured": "succeeded",
            "payment.voided": "cancelled",
        }

        new_status = status_mapping.get(event_type)
        if not new_status:
            logger.warning(f"Unhandled webhook event type: {event_type}")
            return {"success": False, "error": "Unhandled event type"}

        # Get Moyasar payment ID
        moyasar_id = event_data.get("id")
        if not moyasar_id:
            raise ValueError("Missing payment ID in webhook data")

        # Find transaction by Moyasar ID
        transaction = Transaction.objects.filter(
            provider_transaction_id=moyasar_id, wallet_type=wallet_type
        ).first()

        if not transaction:
            logger.warning(f"Transaction not found for Moyasar ID: {moyasar_id}")
            return {"success": False, "error": "Transaction not found"}

        # Update transaction status
        transaction.status = new_status
        transaction.last_verified_at = timezone.now()
        transaction.save()

        logger.info(
            f"Updated transaction {transaction.transaction_id} status to {new_status} from webhook"
        )

        # Return success response
        return {
            "success": True,
            "transaction_id": transaction.transaction_id,
            "moyasar_id": moyasar_id,
            "status": new_status,
            "event_type": event_type,
        }
