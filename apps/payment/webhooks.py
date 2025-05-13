import json
import logging

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .constants import MOYASAR_WEBHOOK_EVENTS
from .models import PaymentLog, Transaction
from .services.moyasar_service import MoyasarService
from .services.payment_service import PaymentService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class MoyasarWebhookView(View):
    """
    Handle Moyasar webhook events
    """

    @method_decorator(require_POST)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Get request body and signature
        try:
            webhook_data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return HttpResponse(status=400)

        signature = request.headers.get("X-Moyasar-Signature")
        moyasar_id = webhook_data.get("id")

        if not moyasar_id:
            logger.error("Missing Moyasar payment ID in webhook data")
            return HttpResponse(status=400)

        # Try to find the transaction to get the transaction type for the correct wallet
        transaction_type = None
        try:
            transaction = Transaction.objects.get(moyasar_id=moyasar_id)
            transaction_type = transaction.transaction_type
            logger.info(
                f"Found transaction {transaction.id} for Moyasar ID {moyasar_id}, type: {transaction_type}"
            )
        except Transaction.DoesNotExist:
            logger.warning(
                f"No transaction found for Moyasar ID {moyasar_id}, using default wallet"
            )

        # Verify webhook signature with the appropriate wallet
        if not MoyasarService.verify_webhook_signature(request.body, signature, transaction_type):
            logger.error("Invalid webhook signature")
            return HttpResponse(status=401)

        # Log webhook event
        event_type = webhook_data.get("type")
        logger.info(
            f"Received Moyasar webhook: {event_type} for wallet type: {transaction_type or 'default'}"
        )

        # Process webhook based on event type
        if event_type in MOYASAR_WEBHOOK_EVENTS:
            try:
                # Handle payment webhook
                PaymentService.handle_payment_webhook(webhook_data)

                # Log webhook processing
                PaymentLog.objects.create(
                    action=f"webhook_{event_type}",
                    details=webhook_data,
                    transaction=transaction if transaction_type else None,
                )

                return HttpResponse(status=200)

            except Exception as e:
                logger.error(f"Error processing webhook: {str(e)}")
                return HttpResponse(status=500)
        else:
            logger.warning(f"Unhandled webhook event type: {event_type}")
            return HttpResponse(status=204)
