"""
Ad Payment Service.

This module handles payment processing for advertisements using the Moyassar
payment gateway.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.marketingapp.models import AdPayment, AdStatus, Advertisement
from apps.payment.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class AdPaymentService:
    """
    Service for processing payments for advertisements
    """

    # Payment type for ads
    PAYMENT_TYPE = "advertisement"

    @classmethod
    def process_payment(
        cls,
        ad_id: str,
        amount: float,
        payment_method: str,
        payment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process payment for an advertisement.

        Args:
            ad_id: ID of the advertisement
            amount: Payment amount in SAR
            payment_method: Payment method (mada, creditcard, applepay, stcpay)
            payment_data: Payment data from Moyassar

        Returns:
            Dictionary with payment result
        """
        try:
            # Get advertisement
            try:
                ad = Advertisement.objects.get(id=ad_id)
            except Advertisement.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Advertisement not found with ID: {ad_id}",
                }

            # Validate advertisement status
            if ad.status not in [AdStatus.DRAFT, AdStatus.PENDING]:
                return {
                    "success": False,
                    "message": f"Advertisement with status '{ad.status}' cannot be paid for",
                }

            # Process payment via PaymentService
            payment_result = PaymentService.process_payment(
                amount=amount,
                payment_method=payment_method,
                payment_data=payment_data,
                payment_type=cls.PAYMENT_TYPE,
                reference_id=str(ad.id),
                description=f"Payment for advertisement: {ad.title}",
            )

            if not payment_result.get("success", False):
                return {
                    "success": False,
                    "message": payment_result.get("message", "Payment processing failed"),
                    "payment_id": payment_result.get("payment_id"),
                }

            # Payment successful, update advertisement
            with transaction.atomic():
                # Create payment record
                payment = AdPayment.objects.create(
                    advertisement=ad,
                    amount=amount,
                    transaction_id=payment_result.get("transaction_id"),
                    payment_method=payment_method,
                    status="completed",
                    invoice_number=cls._generate_invoice_number(ad),
                )

                # Update advertisement
                ad.payment_date = timezone.now()
                ad.amount = amount
                ad.status = AdStatus.PENDING  # Move to pending for admin approval
                ad.save(update_fields=["payment_date", "amount", "status"])

                # If campaign exists, update budget spent
                if ad.campaign:
                    from apps.marketingapp.services.ad_management_service import AdManagementService

                    AdManagementService.update_campaign_budget_spent(ad.campaign.id)

            return {
                "success": True,
                "message": "Payment processed successfully",
                "payment_id": str(payment.id),
                "transaction_id": payment.transaction_id,
                "invoice_number": payment.invoice_number,
            }

        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {"success": False, "message": f"Error processing payment: {str(e)}"}

    @classmethod
    def get_payment_history(
        cls,
        ad_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        shop_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get payment history for advertisements.

        Args:
            ad_id: Optional ID of a specific advertisement
            campaign_id: Optional ID of a campaign
            shop_id: Optional ID of a shop

        Returns:
            Dictionary with payment history
        """
        try:
            # Build query based on provided filters
            query = {}

            if ad_id:
                query["advertisement_id"] = ad_id
            elif campaign_id:
                query["advertisement__campaign_id"] = campaign_id
            elif shop_id:
                query["advertisement__campaign__shop_id"] = shop_id
            else:
                return {
                    "success": False,
                    "message": "At least one filter (ad_id, campaign_id, or shop_id) must be provided",
                }

            # Get payments
            payments = AdPayment.objects.filter(**query).order_by("-payment_date")

            # Format payments for response
            payment_list = []
            for payment in payments:
                payment_list.append(
                    {
                        "payment_id": str(payment.id),
                        "advertisement_id": str(payment.advertisement.id),
                        "advertisement_title": payment.advertisement.title,
                        "amount": float(payment.amount),
                        "payment_method": payment.payment_method,
                        "payment_date": payment.payment_date.isoformat(),
                        "transaction_id": payment.transaction_id,
                        "status": payment.status,
                        "invoice_number": payment.invoice_number,
                    }
                )

            # Calculate totals
            total_amount = sum(payment.amount for payment in payments)

            return {
                "success": True,
                "payments": payment_list,
                "count": len(payment_list),
                "total_amount": float(total_amount),
            }

        except Exception as e:
            logger.error(f"Error getting payment history: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting payment history: {str(e)}",
            }

    @classmethod
    def generate_invoice(cls, payment_id: str) -> Dict[str, Any]:
        """
        Generate invoice details for a payment.

        Args:
            payment_id: ID of the payment

        Returns:
            Dictionary with invoice details
        """
        try:
            # Get payment
            try:
                payment = AdPayment.objects.get(id=payment_id)
            except AdPayment.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Payment not found with ID: {payment_id}",
                }

            # Get advertisement
            ad = payment.advertisement

            # Get campaign and shop info if available
            campaign_name = "N/A"
            shop_name = "N/A"
            company_name = "N/A"

            if ad.campaign:
                campaign_name = ad.campaign.name
                shop_name = ad.campaign.shop.name
                company_name = ad.campaign.company.name

            # Build invoice data
            invoice_data = {
                "invoice_number": payment.invoice_number,
                "date": payment.payment_date.strftime("%Y-%m-%d"),
                "due_date": payment.payment_date.strftime("%Y-%m-%d"),  # Already paid
                "status": "Paid",
                "client": {"company_name": company_name, "shop_name": shop_name},
                "vendor": {
                    "name": "Queue Me",
                    "address": "Queue Me Headquarters, Riyadh, Saudi Arabia",
                    "contact": "billing@queueme.net",
                },
                "items": [
                    {
                        "description": f"Advertisement: {ad.title}",
                        "campaign": campaign_name,
                        "type": ad.ad_type,
                        "amount": float(payment.amount),
                    }
                ],
                "subtotal": float(payment.amount),
                "tax": 0,  # Add tax calculation if needed
                "total": float(payment.amount),
                "payment_method": payment.payment_method,
                "transaction_id": payment.transaction_id,
            }

            return {"success": True, "invoice": invoice_data}

        except Exception as e:
            logger.error(f"Error generating invoice: {str(e)}")
            return {"success": False, "message": f"Error generating invoice: {str(e)}"}

    # Private helper methods

    @staticmethod
    def _generate_invoice_number(ad):
        """
        Generate an invoice number for an advertisement payment.
        """
        # Format: AD-YYYYMMDD-XXXX where XXXX is a unique identifier
        timestamp = timezone.now().strftime("%Y%m%d")
        ad_id_short = str(ad.id)[:8]
        return f"AD-{timestamp}-{ad_id_short}"
