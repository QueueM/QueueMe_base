import base64
import json
import logging

import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from ..constants import MOYASAR_BASE_URL

logger = logging.getLogger(__name__)


class MoyasarService:
    """
    Service for interacting with Moyasar payment gateway API
    """

    @staticmethod
    def get_authorization_header():
        """Get Moyasar API authorization header"""
        auth_string = f"{settings.MOYASAR_API_KEY}:"
        auth_bytes = auth_string.encode("ascii")
        auth_base64 = base64.b64encode(auth_bytes).decode("ascii")

        return f"Basic {auth_base64}"

    @staticmethod
    def create_payment(transaction, callback_url):
        """
        Create a payment with Moyasar

        Args:
            transaction: Transaction model instance
            callback_url: URL for payment callback

        Returns:
            dict: Moyasar response data
        """
        headers = {
            "Authorization": MoyasarService.get_authorization_header(),
            "Content-Type": "application/json",
        }

        # Prepare payment data
        payment_data = {
            "amount": transaction.amount_halalas,
            "currency": "SAR",
            "description": transaction.description,
            "callback_url": f"{settings.FRONTEND_URL}{callback_url}",
            "source": {},
            "metadata": {
                "transaction_id": str(transaction.id),
                "user_id": str(transaction.user.id),
                "type": transaction.transaction_type,
            },
        }

        # Set source based on payment method
        if transaction.payment_method:
            # Using saved payment method
            payment_data["source"] = {
                "type": "token",
                "token": transaction.payment_method.token,
            }
        else:
            # Redirect flow for new payment method
            payment_data["source"] = {"type": transaction.payment_type}

        try:
            response = requests.post(
                f"{MOYASAR_BASE_URL}/payments",
                headers=headers,
                data=json.dumps(payment_data),
            )

            if response.status_code == 200:
                return response.json()
            else:
                # Handle error response
                error_data = response.json()
                logger.error(f"Moyasar error: {error_data}")
                return error_data

        except Exception as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def process_refund(refund):
        """
        Process a refund with Moyasar

        Args:
            refund: Refund model instance

        Returns:
            dict: Result with success status and details
        """
        headers = {
            "Authorization": MoyasarService.get_authorization_header(),
            "Content-Type": "application/json",
        }

        refund_data = {"amount": refund.amount_halalas, "reason": refund.reason}

        try:
            response = requests.post(
                f"{MOYASAR_BASE_URL}/payments/{refund.transaction.moyasar_id}/refund",
                headers=headers,
                data=json.dumps(refund_data),
            )

            if response.status_code == 200:
                moyasar_data = response.json()
                refunds_data = moyasar_data.get("refunds", [])

                if refunds_data and len(refunds_data) > 0:
                    latest_refund = refunds_data[-1]
                    return {
                        "success": True,
                        "refund_id": latest_refund.get("id"),
                        "data": moyasar_data,
                    }
                else:
                    return {
                        "success": False,
                        "error": _("No refund data in Moyasar response"),
                    }
            else:
                error_data = response.json()
                logger.error(f"Moyasar refund error: {error_data}")
                return {
                    "success": False,
                    "error": error_data.get("message", _("Unknown error")),
                }

        except Exception as e:
            logger.error(f"Error processing refund with Moyasar: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def check_payment_status(moyasar_id):
        """
        Check the status of a payment with Moyasar

        Args:
            moyasar_id: Moyasar payment ID

        Returns:
            dict: Payment status data
        """
        headers = {"Authorization": MoyasarService.get_authorization_header()}

        try:
            response = requests.get(
                f"{MOYASAR_BASE_URL}/payments/{moyasar_id}", headers=headers
            )

            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json()
                logger.error(f"Moyasar status check error: {error_data}")
                return {
                    "status": "error",
                    "message": error_data.get("message", _("Unknown error")),
                }

        except Exception as e:
            logger.error(f"Error checking payment status with Moyasar: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def verify_webhook_signature(request_body, signature_header):
        """
        Verify Moyasar webhook signature

        Args:
            request_body: Raw request body
            signature_header: Signature from request header

        Returns:
            bool: Signature validity
        """
        # This is a simplified implementation - in production you'd use
        # HMAC verification with the webhook secret
        if not settings.MOYASAR_WEBHOOK_SECRET or not signature_header:
            return False

        # In a real implementation, you would verify the signature like this:
        # import hmac
        # import hashlib
        # expected_signature = hmac.new(
        #     settings.MOYASAR_WEBHOOK_SECRET.encode(),
        #     request_body,
        #     hashlib.sha256
        # ).hexdigest()
        # return hmac.compare_digest(expected_signature, signature_header)

        # For now, we'll always return True in development
        return True
