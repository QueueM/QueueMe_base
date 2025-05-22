"""
Webhook views for handling payment gateway callbacks.

This module contains webhook handlers for the Moyasar payment gateway,
with separate endpoints for different wallet types:
- Subscription payments
- Advertising payments
- Merchant payments
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payment.services.moyasar_service import MoyasarService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def subscription_webhook(request):
    """
    Webhook handler for subscription payments from Moyasar.

    This endpoint processes callbacks specifically for the subscription wallet.
    It validates the signature and passes the data to the MoyasarService
    for further processing.

    Returns:
        JsonResponse: Response with status 200 if processed successfully
    """
    try:
        # Extract webhook data from the request
        data = json.loads(request.body)

        # Get signature from headers
        signature = request.headers.get("Signature")
        headers = {"Signature": signature} if signature else {}

        # Process the webhook event
        result = MoyasarService.process_webhook(
            data, headers, wallet_type="subscription"
        )

        if result.get("error"):
            logger.error(
                f"Error processing subscription webhook: {result.get('error_message')}"
            )
            return JsonResponse(
                {"status": "error", "message": result.get("error_message")}, status=400
            )

        logger.info(
            f"Successfully processed subscription webhook for payment ID: {data.get('id', 'unknown')}"
        )
        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.exception(f"Unexpected error in subscription webhook: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, status=500
        )


@csrf_exempt
@require_POST
def ads_webhook(request):
    """
    Webhook handler for advertising payments from Moyasar.

    This endpoint processes callbacks specifically for the ads wallet.
    It validates the signature and passes the data to the MoyasarService
    for further processing.

    Returns:
        JsonResponse: Response with status 200 if processed successfully
    """
    try:
        # Extract webhook data from the request
        data = json.loads(request.body)

        # Get signature from headers
        signature = request.headers.get("Signature")
        headers = {"Signature": signature} if signature else {}

        # Process the webhook event
        result = MoyasarService.process_webhook(data, headers, wallet_type="ads")

        if result.get("error"):
            logger.error(f"Error processing ads webhook: {result.get('error_message')}")
            return JsonResponse(
                {"status": "error", "message": result.get("error_message")}, status=400
            )

        logger.info(
            f"Successfully processed ads webhook for payment ID: {data.get('id', 'unknown')}"
        )
        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.exception(f"Unexpected error in ads webhook: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, status=500
        )


@csrf_exempt
@require_POST
def merchant_webhook(request):
    """
    Webhook handler for merchant payments from Moyasar.

    This endpoint processes callbacks specifically for the merchant wallet.
    It validates the signature and passes the data to the MoyasarService
    for further processing.

    Returns:
        JsonResponse: Response with status 200 if processed successfully
    """
    try:
        # Extract webhook data from the request
        data = json.loads(request.body)

        # Get signature from headers
        signature = request.headers.get("Signature")
        headers = {"Signature": signature} if signature else {}

        # Process the webhook event
        result = MoyasarService.process_webhook(data, headers, wallet_type="merchant")

        if result.get("error"):
            logger.error(
                f"Error processing merchant webhook: {result.get('error_message')}"
            )
            return JsonResponse(
                {"status": "error", "message": result.get("error_message")}, status=400
            )

        logger.info(
            f"Successfully processed merchant webhook for payment ID: {data.get('id', 'unknown')}"
        )
        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.exception(f"Unexpected error in merchant webhook: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, status=500
        )
