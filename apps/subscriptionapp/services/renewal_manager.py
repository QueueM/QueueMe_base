# apps/subscriptionapp/services/renewal_manager.py
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.subscriptionapp.constants import (
    RENEWAL_REMINDER_DAYS,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_PAST_DUE,
)
from apps.subscriptionapp.models import Subscription

logger = logging.getLogger(__name__)


class RenewalManager:
    """Service for managing subscription renewals"""

    @staticmethod
    def process_renewal(subscription_id):
        """Process renewal for a subscription"""
        from apps.subscriptionapp.services.subscription_service import SubscriptionService

        subscription = Subscription.objects.get(id=subscription_id)

        # Check if subscription is eligible for renewal
        if subscription.status not in [STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_EXPIRED]:
            logger.warning(
                f"Subscription {subscription_id} not eligible for renewal: status {subscription.status}"
            )
            raise ValueError(_("Subscription is not eligible for renewal"))

        # Initialize payment for the next period
        payment_result = SubscriptionService.initiate_renewal_payment(subscription_id)

        # Log the renewal attempt
        from apps.subscriptionapp.models import SubscriptionLog

        SubscriptionLog.objects.create(
            subscription=subscription,
            action="renewal_attempt",
            metadata={
                "payment_id": payment_result.get("payment_id"),
                "auto": subscription.auto_renew,
            },
        )

        return payment_result

    @staticmethod
    def send_renewal_reminder(subscription_id, days_before):
        """Send renewal reminder for upcoming subscription expiration"""
        subscription = Subscription.objects.get(id=subscription_id)
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(
                f"Cannot send renewal reminder: No contact email for company {company.id}"
            )
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "plan_name": subscription.plan_name or subscription.plan.name,
            "expiry_date": subscription.current_period_end,
            "days_remaining": days_before,
            "auto_renew": subscription.auto_renew,
            "subscription_id": str(subscription.id),
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Renewal Reminder")

        text_content = render_to_string("subscriptionapp/emails/renewal_reminder.txt", context)

        html_content = render_to_string("subscriptionapp/emails/renewal_reminder.html", context)

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Send email
        try:
            email.send()

            # Log reminder sent
            from apps.subscriptionapp.models import SubscriptionLog

            SubscriptionLog.objects.create(
                subscription=subscription,
                action="renewal_reminder_sent",
                metadata={"days_before": days_before, "sent_to": to_email},
            )

            return True
        except Exception as e:
            logger.error(f"Failed to send renewal reminder email: {str(e)}")
            return False

    @staticmethod
    def check_expiring_subscriptions():
        """Check for subscriptions expiring soon and send reminders"""
        for days in RENEWAL_REMINDER_DAYS:
            target_date = timezone.now() + timezone.timedelta(days=days)

            # Find subscriptions expiring around target date
            subscriptions = Subscription.objects.filter(
                status=STATUS_ACTIVE, current_period_end__date=target_date.date()
            )

            reminder_count = 0
            for subscription in subscriptions:
                try:
                    success = RenewalManager.send_renewal_reminder(subscription.id, days)
                    if success:
                        reminder_count += 1
                except Exception as e:
                    logger.error(
                        f"Error sending renewal reminder for subscription {subscription.id}: {str(e)}"
                    )

            logger.info(
                f"Sent {reminder_count} renewal reminders for subscriptions expiring in {days} days"
            )

    @staticmethod
    def process_auto_renewals():
        """Process automatic renewals for active subscriptions"""
        # Find subscriptions due for renewal (within next 24 hours)
        tomorrow = timezone.now() + timezone.timedelta(days=1)

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

        logger.info(f"Processed {renewal_count} subscription auto-renewals")

        return renewal_count
