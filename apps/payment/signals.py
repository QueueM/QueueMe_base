import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PaymentLog, Refund, Transaction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Transaction)
def log_transaction_save(sender, instance, created, **kwargs):
    """Log changes to transactions for audit trail"""
    action = "transaction_created" if created else "transaction_updated"

    try:
        PaymentLog.objects.create(
            transaction=instance,
            action=action,
            user=instance.user,
            details={
                "status": instance.status,
                "amount": str(instance.amount),
                "transaction_type": instance.transaction_type,
            },
        )

        # If transaction succeeded, handle related object updates
        if instance.status == "succeeded":
            from .services.payment_service import PaymentService

            PaymentService.handle_successful_payment(instance)

        # If transaction failed, log the failure
        if instance.status == "failed":
            logger.error(f"Transaction failed: {instance.moyasar_id} - {instance.failure_message}")

    except Exception as e:
        logger.error(f"Error in transaction signal: {str(e)}")


@receiver(post_save, sender=Refund)
def log_refund_save(sender, instance, created, **kwargs):
    """Log changes to refunds for audit trail"""
    action = "refund_created" if created else "refund_updated"

    try:
        PaymentLog.objects.create(
            refund=instance,
            transaction=instance.transaction,
            action=action,
            user=instance.refunded_by,
            details={
                "status": instance.status,
                "amount": str(instance.amount),
                "reason": instance.reason,
            },
        )

        # Update transaction status if refund succeeded
        if instance.status == "succeeded":
            transaction = instance.transaction

            # Calculate total refunded amount
            total_refunded = sum(r.amount for r in transaction.refunds.filter(status="succeeded"))

            # Update transaction status
            if total_refunded >= transaction.amount:
                transaction.status = "refunded"
            else:
                transaction.status = "partially_refunded"

            transaction.save()

    except Exception as e:
        logger.error(f"Error in refund signal: {str(e)}")
