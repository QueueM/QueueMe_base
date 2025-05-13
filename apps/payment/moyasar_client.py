"""
Moyasar Payment Gateway Client

This module provides a client for interacting with the Moyasar payment gateway API
supporting the three wallets (subscription, ads, merchant).
"""

import base64
import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django.conf import settings

from .models import PaymentStatus, PaymentWalletType

logger = logging.getLogger("queueme.payment")

# Moyasar API endpoints
MOYASAR_API_URL = "https://api.moyasar.com/v1"
PAYMENTS_ENDPOINT = f"{MOYASAR_API_URL}/payments"
INVOICES_ENDPOINT = f"{MOYASAR_API_URL}/invoices"
REFUNDS_ENDPOINT = f"{MOYASAR_API_URL}/payments/{{}}/refunds"


class MoyasarClient:
    """
    Client for interacting with Moyasar payment gateway.
    Handles authentication, payment processing, and webhook verification.
    """

    def __init__(self, wallet_type=PaymentWalletType.MERCHANT):
        """
        Initialize the client with credentials based on wallet type

        Args:
            wallet_type: Type of wallet (SUBSCRIPTION, ADS, MERCHANT)
        """
        self.wallet_type = wallet_type

        # Select correct wallet configuration based on type
        if wallet_type == PaymentWalletType.SUBSCRIPTION:
            self.config = settings.MOYASAR_SUB
        elif wallet_type == PaymentWalletType.ADS:
            self.config = settings.MOYASAR_ADS
        else:  # Default to merchant
            self.config = settings.MOYASAR_MER

        self.api_key = self.config["SECRET_KEY"]
        self.auth_header = self._create_auth_header()

    def _create_auth_header(self):
        """Create the Authorization header for API requests"""
        auth_string = f"{self.api_key}:"
        auth_bytes = auth_string.encode("ascii")
        base64_bytes = base64.b64encode(auth_bytes)
        base64_auth = base64_bytes.decode("ascii")
        return {"Authorization": f"Basic {base64_auth}"}

    def process_payment(
        self,
        amount,
        currency,
        source,
        description,
        metadata=None,
        callback_url=None,
        idempotency_key=None,
    ):
        """
        Process a payment through Moyasar

        Args:
            amount: Payment amount in halalas (ریال × 100)
            currency: Currency code (usually 'SAR')
            source: Credit card token or other payment source
            description: Payment description
            metadata: Additional data to store with the payment
            callback_url: URL for payment completion callback
            idempotency_key: Unique key to prevent duplicate payments

        Returns:
            dict: Payment result
        """
        # Convert decimal to integer halalas (Moyasar requires amounts in halalas)
        if isinstance(amount, Decimal):
            amount = int(amount * 100)

        # Prepare request payload
        payload = {
            "amount": amount,
            "currency": currency,
            "source": source,
            "description": description,
        }

        # Add optional fields
        if metadata:
            payload["metadata"] = metadata

        # Add callback URL if provided, otherwise use default from settings
        if callback_url:
            payload["callback_url"] = callback_url
        elif "CALLBACK_URL" in self.config:
            payload["callback_url"] = self.config["CALLBACK_URL"]

        # Set up headers with idempotency key if provided
        headers = self.auth_header.copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            # Make API request
            response = requests.post(PAYMENTS_ENDPOINT, json=payload, headers=headers, timeout=30)

            # Parse response
            result = response.json()

            if response.status_code == 200 and result.get("status") == "paid":
                # Payment successful
                return {
                    "success": True,
                    "transaction_id": result["id"],
                    "status": PaymentStatus.COMPLETED,
                    "amount": Decimal(result["amount"]) / 100,  # Convert from halalas to SAR
                    "currency": result["currency"],
                    "source": result.get("source", {}),
                    "fee": Decimal(result.get("fee", 0)) / 100,
                    "ip": result.get("ip"),
                    "created_at": result.get("created_at"),
                    "raw_response": result,
                }
            else:
                # Payment failed
                logger.error(f"Payment failed: {result}")
                return {
                    "success": False,
                    "error_code": result.get("error", {}).get("type"),
                    "error_message": result.get("error", {}).get("message"),
                    "status": PaymentStatus.FAILED,
                    "raw_response": result,
                }

        except requests.RequestException as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {
                "success": False,
                "error_code": "request_error",
                "error_message": str(e),
                "status": PaymentStatus.FAILED,
            }
        except Exception as e:
            logger.error(f"Unexpected error processing payment: {str(e)}")
            return {
                "success": False,
                "error_code": "unexpected_error",
                "error_message": str(e),
                "status": PaymentStatus.FAILED,
            }

    def process_refund(self, payment_id, amount=None, reason=None, idempotency_key=None):
        """
        Process a refund for a payment

        Args:
            payment_id: The Moyasar payment ID to refund
            amount: Refund amount in SAR (if None, full refund)
            reason: Reason for refund
            idempotency_key: Unique key to prevent duplicate refunds

        Returns:
            dict: Refund result
        """
        # Prepare request payload
        payload = {}

        # Convert to halalas and add to payload if partial refund
        if amount is not None:
            if isinstance(amount, Decimal):
                amount = int(amount * 100)
            payload["amount"] = amount

        if reason:
            payload["reason"] = reason

        # Set up headers with idempotency key if provided
        headers = self.auth_header.copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            # Make API request
            refund_url = REFUNDS_ENDPOINT.format(payment_id)
            response = requests.post(refund_url, json=payload, headers=headers, timeout=30)

            # Parse response
            result = response.json()

            if response.status_code == 200 and result.get("status") == "refunded":
                # Refund successful
                return {
                    "success": True,
                    "refund_id": result["id"],
                    "payment_id": result["payment_id"],
                    "amount": Decimal(result["amount"]) / 100,  # Convert from halalas to SAR
                    "reason": result.get("reason"),
                    "created_at": result.get("created_at"),
                    "raw_response": result,
                }
            else:
                # Refund failed
                logger.error(f"Refund failed: {result}")
                return {
                    "success": False,
                    "error_code": result.get("error", {}).get("type"),
                    "error_message": result.get("error", {}).get("message"),
                    "raw_response": result,
                }

        except requests.RequestException as e:
            logger.error(f"Error processing refund: {str(e)}")
            return {
                "success": False,
                "error_code": "request_error",
                "error_message": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error processing refund: {str(e)}")
            return {
                "success": False,
                "error_code": "unexpected_error",
                "error_message": str(e),
            }

    def get_payment(self, payment_id):
        """
        Get payment details by ID

        Args:
            payment_id: The Moyasar payment ID

        Returns:
            dict: Payment details
        """
        try:
            # Make API request
            response = requests.get(
                f"{PAYMENTS_ENDPOINT}/{payment_id}",
                headers=self.auth_header,
                timeout=30,
            )

            # Parse response
            result = response.json()

            if response.status_code == 200:
                # Request successful
                return {"success": True, "payment": result}
            else:
                # Request failed
                logger.error(f"Error getting payment {payment_id}: {result}")
                return {
                    "success": False,
                    "error_code": result.get("error", {}).get("type"),
                    "error_message": result.get("error", {}).get("message"),
                }

        except requests.RequestException as e:
            logger.error(f"Error retrieving payment: {str(e)}")
            return {
                "success": False,
                "error_code": "request_error",
                "error_message": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving payment: {str(e)}")
            return {
                "success": False,
                "error_code": "unexpected_error",
                "error_message": str(e),
            }

    def verify_webhook_signature(self, signature, payload):
        """
        Verify Moyasar webhook signature

        Args:
            signature: The signature header from the webhook request
            payload: The raw JSON payload from the webhook request

        Returns:
            bool: True if signature is valid
        """
        if not self.api_key or not signature or not payload:
            logger.error("Missing data for webhook verification")
            return False

        try:
            # Get the secret key portion (sk_xxx)
            secret_key = self.api_key

            # Calculate HMAC using SHA256
            computed_signature = hmac.new(
                secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()

            # Compare signatures
            return hmac.compare_digest(computed_signature, signature)

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
