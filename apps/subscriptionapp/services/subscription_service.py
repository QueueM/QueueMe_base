# apps/subscriptionapp/services/subscription_service.py
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.companiesapp.models import Company
from apps.subscriptionapp.constants import (
    PERIOD_TIMEDELTA,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_INITIATED,
    STATUS_PAST_DUE,
    STATUS_TRIAL,
    SUBSCRIPTION_PERIOD_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
)
from apps.subscriptionapp.models import (
    Plan,
    Subscription,
    SubscriptionInvoice,
    SubscriptionLog,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing subscriptions"""

    @staticmethod
    def create_subscription(company_id, plan_id, period="monthly", auto_renew=True):
        """Create a new subscription for a company"""
        company = Company.objects.get(id=company_id)
        plan = Plan.objects.get(id=plan_id)

        # Check if company already has an active subscription
        existing = Subscription.objects.filter(
            company=company, status__in=[STATUS_ACTIVE, STATUS_TRIAL]
        ).first()

        if existing:
            logger.warning(
                f"Company {company_id} already has an active subscription: {existing.id}"
            )
            raise ValueError(_("Company already has an active subscription"))

        # Create subscription in initiated state
        subscription = Subscription.objects.create(
            company=company,
            plan=plan,
            period=period,
            auto_renew=auto_renew,
            status=STATUS_INITIATED,
        )

        # Cache plan details
        subscription.plan_name = plan.name
        subscription.max_shops = plan.max_shops
        subscription.max_services_per_shop = plan.max_services_per_shop
        subscription.max_specialists_per_shop = plan.max_specialists_per_shop
        subscription.save()

        return subscription

    @staticmethod
    def initiate_subscription_payment(
        company_id, plan_id, period="monthly", return_url=None
    ):
        """Initiate payment process for a new subscription"""
        company = Company.objects.get(id=company_id)
        plan = Plan.objects.get(id=plan_id)

        # Calculate price for the period
        from apps.subscriptionapp.utils.billing_utils import calculate_period_price

        amount = calculate_period_price(plan.monthly_price, period)

        # Create or get subscription
        try:
            subscription = Subscription.objects.get(
                company=company, status=STATUS_INITIATED
            )

            # Update subscription if plan or period changed
            if subscription.plan_id != plan_id or subscription.period != period:
                subscription.plan = plan
                subscription.period = period

                # Update cached plan details
                subscription.plan_name = plan.name
                subscription.max_shops = plan.max_shops
                subscription.max_services_per_shop = plan.max_services_per_shop
                subscription.max_specialists_per_shop = plan.max_specialists_per_shop

                subscription.save()
        except Subscription.DoesNotExist:
            # Create new subscription
            subscription = SubscriptionService.create_subscription(
                company_id=company_id, plan_id=plan_id, period=period
            )

        # Set up period dates
        now = timezone.now()
        period_delta = PERIOD_TIMEDELTA.get(period, PERIOD_TIMEDELTA["monthly"])
        period_end = now + period_delta

        # Create invoice
        from apps.subscriptionapp.services.invoice_service import InvoiceService

        invoice = InvoiceService.create_invoice(
            subscription_id=subscription.id,
            amount=amount,
            period_start=now,
            period_end=period_end,
            status="pending",
        )

        # Calculate amount in halalas (1 SAR = 100 halalas)
        amount_halalas = int(Decimal(amount) * 100)

        # Prepare payment data for Moyasar
        payment_data = {
            "amount": amount_halalas,
            "currency": "SAR",
            "description": f"{plan.name} - {period} subscription",
            "callback_url": return_url or settings.MOYASAR_SUB_CALLBACK_URL_COMPLETE,
            "source": {"type": "credit_card"},
            "metadata": {
                "subscription_id": str(subscription.id),
                "invoice_id": str(invoice.id),
                "company_id": str(company.id),
                "plan_id": str(plan.id),
                "period": period,
            },
        }

        # Call Moyasar API to create payment
        headers = {
            "Authorization": f"Basic {SubscriptionService._get_moyasar_auth()}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.moyasar.com/v1/payments",
                headers=headers,
                json=payment_data,
                timeout=30,
            )

            response_data = response.json()

            if response.status_code != 200:
                logger.error(f"Moyasar payment initiation failed: {response_data}")
                raise ValueError(
                    _("Payment initiation failed: ") + response_data.get("message", "")
                )

            # Update invoice with transaction data
            moyasar_id = response_data.get("id")
            payment_url = response_data.get("source", {}).get("transaction_url")

            # Create transaction record
            from apps.payment.models import Transaction

            transaction = Transaction.objects.create(
                moyasar_id=moyasar_id,
                amount=amount,
                amount_halalas=amount_halalas,
                user=company.owner,  # Use company owner as the user
                payment_type="credit_card",
                status="initiated",
                transaction_type="subscription",
                description=f"{plan.name} - {period} subscription",
                metadata=response_data,
                # Generic relation to subscription
                content_type=ContentType.objects.get_for_model(Subscription),
                object_id=subscription.id,
            )

            # Link transaction to invoice
            invoice.transaction = transaction
            invoice.save()

            # Return payment details
            return {
                "subscription_id": str(subscription.id),
                "invoice_id": str(invoice.id),
                "payment_id": moyasar_id,
                "payment_url": payment_url,
                "amount": amount,
            }

        except requests.RequestException as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            raise ValueError(_("Payment service communication error"))

    @staticmethod
    def initiate_renewal_payment(subscription_id):
        """Initiate payment for subscription renewal"""
        subscription = Subscription.objects.get(id=subscription_id)

        # Calculate price for the period
        from apps.subscriptionapp.utils.billing_utils import calculate_period_price

        amount = calculate_period_price(
            subscription.plan.monthly_price, subscription.period
        )

        # Set up period dates
        current_end = subscription.current_period_end or timezone.now()
        period_delta = PERIOD_TIMEDELTA.get(
            subscription.period, PERIOD_TIMEDELTA["monthly"]
        )
        period_end = current_end + period_delta

        # Create invoice
        from apps.subscriptionapp.services.invoice_service import InvoiceService

        invoice = InvoiceService.create_invoice(
            subscription_id=subscription.id,
            amount=amount,
            period_start=current_end,
            period_end=period_end,
            status="pending",
        )

        # Calculate amount in halalas (1 SAR = 100 halalas)
        amount_halalas = int(Decimal(amount) * 100)

        # Prepare payment data for Moyasar
        payment_data = {
            "amount": amount_halalas,
            "currency": "SAR",
            "description": f"{subscription.plan_name} - {subscription.period} subscription renewal",
            "callback_url": settings.MOYASAR_SUB_CALLBACK_URL_COMPLETE,
            "source": {"type": "credit_card"},
            "metadata": {
                "subscription_id": str(subscription.id),
                "invoice_id": str(invoice.id),
                "company_id": str(subscription.company.id),
                "plan_id": str(subscription.plan.id),
                "period": subscription.period,
                "renewal": "true",
            },
        }

        # Call Moyasar API to create payment
        headers = {
            "Authorization": f"Basic {SubscriptionService._get_moyasar_auth()}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.moyasar.com/v1/payments",
                headers=headers,
                json=payment_data,
                timeout=30,
            )

            response_data = response.json()

            if response.status_code != 200:
                logger.error(
                    f"Moyasar renewal payment initiation failed: {response_data}"
                )
                raise ValueError(
                    _("Renewal payment initiation failed: ")
                    + response_data.get("message", "")
                )

            # Get payment details
            moyasar_id = response_data.get("id")
            payment_url = response_data.get("source", {}).get("transaction_url")

            # Create transaction record
            from apps.payment.models import Transaction

            transaction = Transaction.objects.create(
                moyasar_id=moyasar_id,
                amount=amount,
                amount_halalas=amount_halalas,
                user=subscription.company.owner,  # Use company owner as the user
                payment_type="credit_card",
                status="initiated",
                transaction_type="subscription",
                description=f"{subscription.plan_name} - {subscription.period} subscription renewal",
                metadata=response_data,
                # Generic relation to subscription
                content_type=ContentType.objects.get_for_model(Subscription),
                object_id=subscription.id,
            )

            # Link transaction to invoice
            invoice.transaction = transaction
            invoice.save()

            # Return payment details
            return {
                "subscription_id": str(subscription.id),
                "invoice_id": str(invoice.id),
                "payment_id": moyasar_id,
                "payment_url": payment_url,
                "amount": amount,
            }

        except requests.RequestException as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            raise ValueError(_("Payment service communication error"))

    @staticmethod
    def handle_successful_payment(payment_id):
        """Handle successful payment webhook from Moyasar"""
        # Get payment details from Moyasar
        headers = {"Authorization": f"Basic {SubscriptionService._get_moyasar_auth()}"}

        try:
            response = requests.get(
                f"https://api.moyasar.com/v1/payments/{payment_id}",
                headers=headers,
                timeout=30,
            )

            response_data = response.json()

            if response.status_code != 200:
                logger.error(
                    f"Failed to get payment details from Moyasar: {response_data}"
                )
                return False

            # Get metadata
            metadata = response_data.get("metadata", {})
            subscription_id = metadata.get("subscription_id")
            invoice_id = metadata.get("invoice_id")
            is_renewal = metadata.get("renewal") == "true"

            if not subscription_id or not invoice_id:
                logger.error(
                    f"Missing subscription_id or invoice_id in payment metadata: {metadata}"
                )
                return False

            # Get subscription and invoice
            subscription = Subscription.objects.get(id=subscription_id)
            invoice = SubscriptionInvoice.objects.get(id=invoice_id)

            # Update transaction status
            from apps.payment.models import Transaction

            transaction = Transaction.objects.get(moyasar_id=payment_id)
            transaction.status = "succeeded"
            transaction.save()

            # Update invoice status
            from apps.subscriptionapp.services.invoice_service import InvoiceService

            InvoiceService.update_invoice_status(
                invoice_id=invoice.id,
                new_status="paid",
                transaction=transaction,
                paid_date=timezone.now(),
            )

            # If initial subscription payment
            if subscription.status == STATUS_INITIATED:
                # Activate subscription
                return SubscriptionService.activate_subscription(subscription_id)

            # If renewal payment
            elif is_renewal:
                # Extend subscription period
                return SubscriptionService.extend_subscription_period(
                    subscription_id=subscription_id, invoice_id=invoice_id
                )

            # Handle past due subscription becoming active again
            elif subscription.status == STATUS_PAST_DUE:
                # Reactivate subscription
                subscription.status = STATUS_ACTIVE
                subscription.save()

                # Log status change
                SubscriptionLog.objects.create(
                    subscription=subscription,
                    action="status_change",
                    status_before=STATUS_PAST_DUE,
                    status_after=STATUS_ACTIVE,
                    metadata={"payment_id": payment_id, "invoice_id": str(invoice.id)},
                )

            return True

        except requests.RequestException as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            return False
        except (Subscription.DoesNotExist, SubscriptionInvoice.DoesNotExist) as e:
            logger.error(f"Entity not found: {str(e)}")
            return False

    @staticmethod
    def handle_failed_payment(payment_id):
        """Handle failed payment webhook from Moyasar"""
        # Get payment details from Moyasar
        headers = {"Authorization": f"Basic {SubscriptionService._get_moyasar_auth()}"}

        try:
            response = requests.get(
                f"https://api.moyasar.com/v1/payments/{payment_id}",
                headers=headers,
                timeout=30,
            )

            response_data = response.json()

            if response.status_code != 200:
                logger.error(
                    f"Failed to get payment details from Moyasar: {response_data}"
                )
                return False

            # Get metadata
            metadata = response_data.get("metadata", {})
            subscription_id = metadata.get("subscription_id")
            invoice_id = metadata.get("invoice_id")
            is_renewal = metadata.get("renewal") == "true"

            if not subscription_id or not invoice_id:
                logger.error(
                    f"Missing subscription_id or invoice_id in payment metadata: {metadata}"
                )
                return False

            # Get subscription and invoice
            subscription = Subscription.objects.get(id=subscription_id)
            invoice = SubscriptionInvoice.objects.get(id=invoice_id)

            # Update transaction status
            from apps.payment.models import Transaction

            transaction = Transaction.objects.get(moyasar_id=payment_id)
            transaction.status = "failed"
            transaction.save()

            # Update invoice status
            from apps.subscriptionapp.services.invoice_service import InvoiceService

            InvoiceService.update_invoice_status(
                invoice_id=invoice.id, new_status="failed", transaction=transaction
            )

            # If renewal payment failed for active subscription
            if is_renewal and subscription.status == STATUS_ACTIVE:
                # Set subscription to past due
                subscription.status = STATUS_PAST_DUE
                subscription.save()

                # Log status change
                SubscriptionLog.objects.create(
                    subscription=subscription,
                    action="status_change",
                    status_before=STATUS_ACTIVE,
                    status_after=STATUS_PAST_DUE,
                    metadata={
                        "payment_id": payment_id,
                        "invoice_id": str(invoice.id),
                        "reason": "renewal_payment_failed",
                    },
                )

            return True

        except requests.RequestException as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            return False
        except (Subscription.DoesNotExist, SubscriptionInvoice.DoesNotExist) as e:
            logger.error(f"Entity not found: {str(e)}")
            return False

    @staticmethod
    def activate_subscription(subscription_id):
        """Activate a subscription after successful initial payment"""
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.status != STATUS_INITIATED:
            logger.warning(
                f"Subscription {subscription_id} not in initiated status: {subscription.status}"
            )
            return False

        # Set subscription dates
        now = timezone.now()
        period_delta = PERIOD_TIMEDELTA.get(
            subscription.period, PERIOD_TIMEDELTA["monthly"]
        )

        subscription.status = STATUS_ACTIVE
        subscription.start_date = now
        subscription.current_period_start = now
        subscription.current_period_end = now + period_delta
        subscription.save()

        # Log activation
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="status_change",
            status_before=STATUS_INITIATED,
            status_after=STATUS_ACTIVE,
            metadata={
                "period_start": subscription.current_period_start.isoformat(),
                "period_end": subscription.current_period_end.isoformat(),
            },
        )

        # Initialize feature usage records
        from apps.subscriptionapp.services.usage_monitor import UsageMonitor

        UsageMonitor.initialize_usage_tracking(subscription_id)

        # Send confirmation email
        SubscriptionService.send_confirmation_email(subscription_id)

        return True

    @staticmethod
    def extend_subscription_period(subscription_id, invoice_id):
        """Extend subscription period after successful renewal payment"""
        subscription = Subscription.objects.get(id=subscription_id)
        invoice = SubscriptionInvoice.objects.get(id=invoice_id)

        if subscription.status not in [STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_EXPIRED]:
            logger.warning(
                f"Subscription {subscription_id} cannot be extended: {subscription.status}"
            )
            return False

        # Get the period dates from the invoice
        period_start = invoice.period_start
        period_end = invoice.period_end

        # Update subscription
        old_status = subscription.status

        subscription.status = STATUS_ACTIVE
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.save()

        # Log extension
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="period_extended",
            status_before=old_status,
            status_after=STATUS_ACTIVE,
            metadata={
                "invoice_id": str(invoice.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        # If status changed, log it
        if old_status != STATUS_ACTIVE:
            SubscriptionLog.objects.create(
                subscription=subscription,
                action="status_change",
                status_before=old_status,
                status_after=STATUS_ACTIVE,
                metadata={
                    "invoice_id": str(invoice.id),
                    "reason": "renewal_payment_succeeded",
                },
            )

        return True

    # apps/subscriptionapp/services/subscription_service.py (continued)
    @staticmethod
    def cancel_subscription(subscription_id, performed_by=None, reason=""):
        """Cancel a subscription"""
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.status not in [STATUS_ACTIVE, STATUS_TRIAL, STATUS_PAST_DUE]:
            logger.warning(
                f"Subscription {subscription_id} cannot be canceled: {subscription.status}"
            )
            raise ValueError(_("Subscription cannot be canceled in its current state"))

        old_status = subscription.status

        # Update subscription
        subscription.status = STATUS_CANCELED
        subscription.canceled_at = timezone.now()
        subscription.auto_renew = False
        subscription.save()

        # Log cancellation
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="status_change",
            status_before=old_status,
            status_after=STATUS_CANCELED,
            performed_by=performed_by,
            metadata={
                "reason": reason,
                "canceled_at": subscription.canceled_at.isoformat(),
            },
        )

        # Cancel in Moyasar if there's a moyasar_id
        if subscription.moyasar_id:
            SubscriptionService._cancel_moyasar_subscription(subscription.moyasar_id)

        # Send cancellation email
        SubscriptionService.send_cancellation_email(subscription_id)

        return True

    @staticmethod
    def expire_subscription(subscription_id):
        """Mark a subscription as expired"""
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.status != STATUS_PAST_DUE:
            logger.warning(
                f"Subscription {subscription_id} cannot be expired: {subscription.status}"
            )
            return False

        # Update subscription
        subscription.status = STATUS_EXPIRED
        subscription.save()

        # Log expiration
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="status_change",
            status_before=STATUS_PAST_DUE,
            status_after=STATUS_EXPIRED,
            metadata={
                "expired_at": timezone.now().isoformat(),
                "reason": "past_due_grace_period_exceeded",
            },
        )

        # Send expiration email
        SubscriptionService.send_expiration_email(subscription_id)

        return True

    @staticmethod
    def change_plan(subscription_id, new_plan_id, performed_by=None):
        """Change a subscription's plan"""
        subscription = Subscription.objects.get(id=subscription_id)
        new_plan = Plan.objects.get(id=new_plan_id)

        if subscription.status not in [STATUS_ACTIVE, STATUS_TRIAL]:
            logger.warning(
                f"Cannot change plan for subscription {subscription_id}: {subscription.status}"
            )
            raise ValueError(
                _("Plan can only be changed for active or trial subscriptions")
            )

        old_plan_id = subscription.plan_id
        old_plan_name = subscription.plan_name

        # Update subscription
        subscription.plan = new_plan
        subscription.plan_name = new_plan.name
        subscription.max_shops = new_plan.max_shops
        subscription.max_services_per_shop = new_plan.max_services_per_shop
        subscription.max_specialists_per_shop = new_plan.max_specialists_per_shop
        subscription.save()

        # Log plan change
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="plan_change",
            performed_by=performed_by,
            metadata={
                "old_plan_id": str(old_plan_id),
                "old_plan_name": old_plan_name,
                "new_plan_id": str(new_plan_id),
                "new_plan_name": new_plan.name,
            },
        )

        # Update feature usage limits
        from apps.subscriptionapp.services.usage_monitor import UsageMonitor

        UsageMonitor.update_usage_limits(subscription_id)

        # Send plan change email
        SubscriptionService.send_plan_change_email(subscription_id, old_plan_name)

        return True

    @staticmethod
    def change_period(subscription_id, new_period, performed_by=None):
        """Change a subscription's billing period"""
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.status not in [STATUS_ACTIVE, STATUS_TRIAL]:
            logger.warning(
                f"Cannot change period for subscription {subscription_id}: {subscription.status}"
            )
            raise ValueError(
                _("Period can only be changed for active or trial subscriptions")
            )

        if new_period not in dict(SUBSCRIPTION_PERIOD_CHOICES):
            raise ValueError(_("Invalid subscription period"))

        old_period = subscription.period

        # Update subscription
        subscription.period = new_period
        subscription.save()

        # Log period change
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="period_change",
            performed_by=performed_by,
            metadata={"old_period": old_period, "new_period": new_period},
        )

        return True

    @staticmethod
    def change_status(subscription_id, new_status, performed_by=None):
        """Manually change a subscription's status (admin only)"""
        subscription = Subscription.objects.get(id=subscription_id)

        if new_status not in dict(SUBSCRIPTION_STATUS_CHOICES):
            raise ValueError(_("Invalid subscription status"))

        old_status = subscription.status

        # Update subscription
        subscription.status = new_status

        # Handle status-specific updates
        if new_status == STATUS_ACTIVE and not subscription.current_period_end:
            # Set period dates for new active subscription
            now = timezone.now()
            period_delta = PERIOD_TIMEDELTA.get(
                subscription.period, PERIOD_TIMEDELTA["monthly"]
            )

            subscription.start_date = now
            subscription.current_period_start = now
            subscription.current_period_end = now + period_delta

        elif new_status == STATUS_CANCELED and not subscription.canceled_at:
            subscription.canceled_at = timezone.now()
            subscription.auto_renew = False

        elif new_status == STATUS_TRIAL and not subscription.trial_end:
            # Set default trial period (14 days)
            subscription.trial_end = timezone.now() + timezone.timedelta(days=14)

        subscription.save()

        # Log status change
        SubscriptionLog.objects.create(
            subscription=subscription,
            action="status_change",
            status_before=old_status,
            status_after=new_status,
            performed_by=performed_by,
            metadata={"manual_change": True},
        )

        return True

    @staticmethod
    def retry_payment(subscription_id):
        """Retry payment for a past due subscription"""
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.status != STATUS_PAST_DUE:
            logger.warning(
                f"Cannot retry payment for subscription {subscription_id}: {subscription.status}"
            )
            raise ValueError(
                _("Payment can only be retried for past due subscriptions")
            )

        # Initiate renewal payment
        return SubscriptionService.initiate_renewal_payment(subscription_id)

    @staticmethod
    def send_confirmation_email(subscription_id):
        """Send subscription confirmation email"""
        subscription = Subscription.objects.get(id=subscription_id)
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(
                f"Cannot send confirmation email: No contact email for company {company.id}"
            )
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "plan_name": subscription.plan_name or subscription.plan.name,
            "start_date": subscription.start_date,
            "end_date": subscription.current_period_end,
            "period": subscription.period,
            "auto_renew": subscription.auto_renew,
            "subscription_id": str(subscription.id),
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Confirmation")

        text_content = render_to_string(
            "subscriptionapp/emails/subscription_confirmation.txt", context
        )

        html_content = render_to_string(
            "subscriptionapp/emails/subscription_confirmation.html", context
        )

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Send email
        try:
            email.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")
            return False

    @staticmethod
    def send_cancellation_email(subscription_id):
        """Send subscription cancellation email"""
        subscription = Subscription.objects.get(id=subscription_id)
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(
                f"Cannot send cancellation email: No contact email for company {company.id}"
            )
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "plan_name": subscription.plan_name or subscription.plan.name,
            "canceled_at": subscription.canceled_at,
            "end_date": subscription.current_period_end,
            "subscription_id": str(subscription.id),
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Cancellation")

        # In a real implementation, you would use actual template files
        text_content = "Your subscription has been canceled"
        html_content = "<p>Your subscription has been canceled</p>"

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Send email
        try:
            email.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send cancellation email: {str(e)}")
            return False

    @staticmethod
    def send_expiration_email(subscription_id):
        """Send subscription expiration email"""
        subscription = Subscription.objects.get(id=subscription_id)
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(
                f"Cannot send expiration email: No contact email for company {company.id}"
            )
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "plan_name": subscription.plan_name or subscription.plan.name,
            "expired_at": timezone.now(),
            "subscription_id": str(subscription.id),
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Has Expired")

        # In a real implementation, you would use actual template files
        text_content = "Your subscription has expired"
        html_content = "<p>Your subscription has expired</p>"

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Send email
        try:
            email.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send expiration email: {str(e)}")
            return False

    @staticmethod
    def send_plan_change_email(subscription_id, old_plan_name):
        """Send plan change email"""
        subscription = Subscription.objects.get(id=subscription_id)
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(
                f"Cannot send plan change email: No contact email for company {company.id}"
            )
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "old_plan_name": old_plan_name,
            "new_plan_name": subscription.plan_name or subscription.plan.name,
            "changed_at": timezone.now(),
            "subscription_id": str(subscription.id),
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Plan Has Changed")

        # In a real implementation, you would use actual template files
        text_content = "Your subscription plan has changed"
        html_content = "<p>Your subscription plan has changed</p>"

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Send email
        try:
            email.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send plan change email: {str(e)}")
            return False

    @staticmethod
    def _get_moyasar_auth():
        """Get Moyasar API authentication string"""
        api_key = settings.MOYASAR_SUB_SECRET
        import base64

        return base64.b64encode(f"{api_key}:".encode()).decode()

    @staticmethod
    def _cancel_moyasar_subscription(moyasar_id):
        """Cancel a subscription in Moyasar"""
        headers = {
            "Authorization": f"Basic {SubscriptionService._get_moyasar_auth()}",
            "Content-Type": "application/json",
        }

        try:
            # This is a placeholder - Moyasar doesn't actually have a subscription API
            # In a real implementation, you would call the appropriate endpoint
            # response = requests.post(
            #     f'https://api.moyasar.com/v1/subscriptions/{moyasar_id}/cancel',
            #     headers=headers
            # )

            # Just log for now
            logger.info(f"Would cancel Moyasar subscription: {moyasar_id}")
            return True

        except requests.RequestException as e:
            logger.error(f"Error calling Moyasar API: {str(e)}")
            return False

    @staticmethod
    def handle_subscription_created(moyasar_id):
        """Handle subscription created webhook from Moyasar"""
        # Placeholder for handling Moyasar subscription events
        logger.info(f"Handling subscription created: {moyasar_id}")
        return True

    @staticmethod
    def handle_subscription_updated(moyasar_id):
        """Handle subscription updated webhook from Moyasar"""
        # Placeholder for handling Moyasar subscription events
        logger.info(f"Handling subscription updated: {moyasar_id}")
        return True

    @staticmethod
    def handle_subscription_canceled(moyasar_id):
        """Handle subscription canceled webhook from Moyasar"""
        # Placeholder for handling Moyasar subscription events
        logger.info(f"Handling subscription canceled: {moyasar_id}")
        return True
