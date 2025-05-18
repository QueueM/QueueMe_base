# apps/subscriptionapp/webhooks.py
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .constants import (
    EVENT_PAYMENT_FAILED,
    EVENT_PAYMENT_SUCCEEDED,
    EVENT_SUBSCRIPTION_CANCELED,
    EVENT_SUBSCRIPTION_CREATED,
    EVENT_SUBSCRIPTION_UPDATED,
)
from .services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


def verify_webhook_signature(request):
    """Verify Moyasar webhook signature"""
    webhook_secret = settings.MOYASAR_SUB_WEBHOOK_SECRET
    signature = request.headers.get("Signature")

    if not signature:
        logger.warning("Webhook request missing signature")
        return False

    computed_signature = hmac.new(
        webhook_secret.encode("utf-8"), request.body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)


@csrf_exempt
@require_POST
def subscription_webhook(request):
    """Handle webhooks from Moyasar for subscription events"""
    # Verify webhook signature (for security)
    if not verify_webhook_signature(request):
        logger.warning("Invalid webhook signature")
        return HttpResponse(status=403)

    try:
        data = json.loads(request.body)
        event_type = data.get("type")

        logger.info(f"Received webhook: {event_type}")

        if event_type == EVENT_PAYMENT_SUCCEEDED:
            # Process successful payment
            payment_id = data.get("data", {}).get("id")
            SubscriptionService.handle_successful_payment(payment_id)

        elif event_type == EVENT_PAYMENT_FAILED:
            # Process failed payment
            payment_id = data.get("data", {}).get("id")
            SubscriptionService.handle_failed_payment(payment_id)

        elif event_type == EVENT_SUBSCRIPTION_CREATED:
            # Process subscription created
            subscription_id = data.get("data", {}).get("id")
            SubscriptionService.handle_subscription_created(subscription_id)

        elif event_type == EVENT_SUBSCRIPTION_UPDATED:
            # Process subscription updated
            subscription_id = data.get("data", {}).get("id")
            SubscriptionService.handle_subscription_updated(subscription_id)

        elif event_type == EVENT_SUBSCRIPTION_CANCELED:
            # Process subscription canceled
            subscription_id = data.get("data", {}).get("id")
            SubscriptionService.handle_subscription_canceled(subscription_id)

        else:
            logger.info(f"Unhandled webhook event type: {event_type}")

        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return HttpResponse(status=400)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)
