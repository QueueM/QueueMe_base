# apps/subscriptionapp/tasks.py
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def process_subscription_renewals():
    """Process automatic subscription renewals for active subscriptions approaching end date"""
    from apps.subscriptionapp.constants import STATUS_ACTIVE
    from apps.subscriptionapp.models import Subscription
    from apps.subscriptionapp.services.renewal_manager import RenewalManager

    # Find subscriptions due for renewal (within next 24 hours)
    tomorrow = timezone.now() + timedelta(days=1)

    subscriptions_to_renew = Subscription.objects.filter(
        status=STATUS_ACTIVE, auto_renew=True, current_period_end__lte=tomorrow
    )

    renewal_count = 0
    for subscription in subscriptions_to_renew:
        try:
            RenewalManager.process_renewal(subscription.id)
            renewal_count += 1
        except Exception as e:
            logger.error(f"Error renewing subscription {subscription.id}: {str(e)}")

    return f"Processed {renewal_count} subscription renewals"


@shared_task
def check_past_due_subscriptions():
    """Check past due subscriptions and expire them if grace period has passed"""
    from apps.subscriptionapp.constants import (
        PAST_DUE_GRACE_PERIOD_DAYS,
        STATUS_PAST_DUE,
    )
    from apps.subscriptionapp.models import Subscription
    from apps.subscriptionapp.services.subscription_service import SubscriptionService

    # Find past due subscriptions beyond grace period
    grace_end = timezone.now() - timedelta(days=PAST_DUE_GRACE_PERIOD_DAYS)

    past_due_subscriptions = Subscription.objects.filter(
        status=STATUS_PAST_DUE, updated_at__lte=grace_end
    )

    expired_count = 0
    for subscription in past_due_subscriptions:
        try:
            SubscriptionService.expire_subscription(subscription.id)
            expired_count += 1
        except Exception as e:
            logger.error(f"Error expiring subscription {subscription.id}: {str(e)}")

    return f"Expired {expired_count} past due subscriptions"


@shared_task
def send_renewal_reminders():
    """Send renewal reminders for subscriptions approaching expiration"""
    from apps.subscriptionapp.constants import RENEWAL_REMINDER_DAYS, STATUS_ACTIVE
    from apps.subscriptionapp.models import Subscription
    from apps.subscriptionapp.services.renewal_manager import RenewalManager

    reminder_count = 0

    # Process each reminder interval
    for days in RENEWAL_REMINDER_DAYS:
        target_date = timezone.now() + timedelta(days=days)

        # Find subscriptions expiring around target date
        subscriptions = Subscription.objects.filter(
            status=STATUS_ACTIVE, current_period_end__date=target_date.date()
        )

        for subscription in subscriptions:
            try:
                RenewalManager.send_renewal_reminder(subscription.id, days)
                reminder_count += 1
            except Exception as e:
                logger.error(
                    f"Error sending renewal reminder for subscription {subscription.id}: {str(e)}"
                )

    return f"Sent {reminder_count} renewal reminders"


@shared_task
def update_usage_statistics():
    """Update usage statistics for all active subscriptions"""
    from apps.subscriptionapp.constants import STATUS_ACTIVE, STATUS_TRIAL
    from apps.subscriptionapp.models import Subscription
    from apps.subscriptionapp.services.usage_monitor import UsageMonitor

    # Get all active subscriptions
    subscriptions = Subscription.objects.filter(
        status__in=[STATUS_ACTIVE, STATUS_TRIAL]
    )

    update_count = 0
    for subscription in subscriptions:
        try:
            company_id = subscription.company_id
            UsageMonitor.update_all_usage(company_id)
            update_count += 1
        except Exception as e:
            logger.error(
                f"Error updating usage for subscription {subscription.id}: {str(e)}"
            )

    return f"Updated usage statistics for {update_count} subscriptions"


@shared_task
def retry_failed_payments():
    """Retry failed subscription payments"""
    from apps.subscriptionapp.constants import (
        MAX_PAYMENT_RETRY_ATTEMPTS,
        STATUS_PAST_DUE,
    )
    from apps.subscriptionapp.models import Subscription, SubscriptionInvoice
    from apps.subscriptionapp.services.subscription_service import SubscriptionService

    # Get past due subscriptions with failed payments
    past_due_subscriptions = Subscription.objects.filter(status=STATUS_PAST_DUE)

    retry_count = 0
    for subscription in past_due_subscriptions:
        # Check if we haven't exceeded the maximum retry attempts
        failed_attempts = SubscriptionInvoice.objects.filter(
            subscription=subscription, status="failed"
        ).count()

        if failed_attempts < MAX_PAYMENT_RETRY_ATTEMPTS:
            try:
                SubscriptionService.retry_payment(subscription.id)
                retry_count += 1
            except Exception as e:
                logger.error(
                    f"Error retrying payment for subscription {subscription.id}: {str(e)}"
                )

    return f"Retried {retry_count} failed payments"
