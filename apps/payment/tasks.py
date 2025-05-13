import logging

from celery import shared_task
from django.utils import timezone

from .models import Refund, Transaction
from .services.moyasar_service import MoyasarService

logger = logging.getLogger(__name__)


@shared_task
def process_pending_refunds():
    """Process any pending refunds in the system"""
    pending_refunds = Refund.objects.filter(status="initiated")

    for refund in pending_refunds:
        try:
            # Check if transaction exists and is in correct state
            if not refund.transaction or refund.transaction.status not in [
                "succeeded",
                "partially_refunded",
            ]:
                refund.status = "failed"
                refund.failure_message = "Invalid transaction state for refund"
                refund.save()
                continue

            # Call Moyasar to process refund
            result = MoyasarService.process_refund(refund)

            if result.get("success"):
                refund.moyasar_id = result.get("refund_id")
                refund.status = "succeeded"
            else:
                refund.status = "failed"
                refund.failure_message = result.get("error")

            refund.save()

        except Exception as e:
            logger.error(f"Error processing refund {refund.id}: {str(e)}")
            refund.status = "failed"
            refund.failure_message = str(e)
            refund.save()


@shared_task
def check_pending_transactions():
    """Check status of pending transactions that may have timed out"""
    # Look for transactions that have been initiated for more than 15 minutes
    cutoff_time = timezone.now() - timezone.timedelta(minutes=15)
    pending_transactions = Transaction.objects.filter(
        status="initiated", created_at__lt=cutoff_time
    )

    for transaction in pending_transactions:
        try:
            # Check status with Moyasar
            status = MoyasarService.check_payment_status(transaction.moyasar_id)

            if status.get("status") != "initiated":
                # Update transaction status
                if status.get("status") == "paid":
                    transaction.status = "succeeded"
                else:
                    transaction.status = "failed"
                    transaction.failure_message = status.get("message", "Transaction timed out")

                transaction.metadata.update(status)
                transaction.save()

        except Exception as e:
            logger.error(f"Error checking transaction {transaction.id}: {str(e)}")


@shared_task
def generate_payment_reports():
    """Generate daily payment reports"""
    # This would generate reports and potentially email them to admins
    logger.info("Generating payment reports")
    # Implementation depends on specific reporting needs
