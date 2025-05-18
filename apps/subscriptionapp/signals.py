# apps/subscriptionapp/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

from .constants import STATUS_ACTIVE
from .models import Subscription, SubscriptionInvoice


@receiver(post_save, sender=Subscription)
def create_subscription_log(sender, instance, created, **kwargs):
    """Create subscription log entry when subscription is created or updated"""
    from .models import SubscriptionLog

    if created:
        # New subscription created
        SubscriptionLog.objects.create(
            subscription=instance, action="created", status_after=instance.status
        )
    else:
        # Log recent changes
        changed_fields = instance.tracker.changed()

        if "status" in changed_fields:
            SubscriptionLog.objects.create(
                subscription=instance,
                action="status_change",
                status_before=changed_fields["status"],
                status_after=instance.status,
            )

        if "plan_id" in changed_fields:
            SubscriptionLog.objects.create(
                subscription=instance,
                action="plan_change",
                metadata={
                    "old_plan_id": str(changed_fields["plan_id"]),
                    "new_plan_id": str(instance.plan_id),
                },
            )


@receiver(post_save, sender=Subscription)
def update_feature_usage(sender, instance, created, **kwargs):
    """Create/update feature usage records when subscription is created or updated"""
    from .models import FeatureUsage

    if created or instance.status == STATUS_ACTIVE:
        # Create/update feature usage records
        FeatureUsage.objects.update_or_create(
            subscription=instance,
            feature_category="shops",
            defaults={"limit": instance.max_shops},
        )

        FeatureUsage.objects.update_or_create(
            subscription=instance,
            feature_category="services",
            defaults={"limit": instance.max_services_per_shop},
        )

        FeatureUsage.objects.update_or_create(
            subscription=instance,
            feature_category="specialists",
            defaults={"limit": instance.max_specialists_per_shop},
        )


@receiver(post_save, sender=Shop)
def update_shop_usage(sender, instance, created, **kwargs):
    """Update shop usage count when a shop is created"""
    if created:
        from apps.subscriptionapp.services.usage_monitor import UsageMonitor

        # Update shop usage for the company
        company = instance.company
        UsageMonitor.update_shop_usage(company.id)


@receiver(post_save, sender=Service)
def update_service_usage(sender, instance, created, **kwargs):
    """Update service usage count when a service is created"""
    if created:
        from apps.subscriptionapp.services.usage_monitor import UsageMonitor

        # Update service usage for the shop
        shop = instance.shop
        UsageMonitor.update_service_usage(shop.company.id, shop.id)


@receiver(post_save, sender=Specialist)
def update_specialist_usage(sender, instance, created, **kwargs):
    """Update specialist usage count when a specialist is created"""
    if created:
        from apps.subscriptionapp.services.usage_monitor import UsageMonitor

        # Update specialist usage for the shop
        shop = instance.employee.shop
        UsageMonitor.update_specialist_usage(shop.company.id, shop.id)


@receiver(pre_save, sender=Subscription)
def update_cached_plan_details(sender, instance, **kwargs):
    """Cache plan details when subscription is created/updated"""
    if instance.plan and (not instance.plan_name or instance.plan_name != instance.plan.name):
        # Cache plan details
        instance.plan_name = instance.plan.name
        instance.max_shops = instance.plan.max_shops
        instance.max_services_per_shop = instance.plan.max_services_per_shop
        instance.max_specialists_per_shop = instance.plan.max_specialists_per_shop


@receiver(post_save, sender=SubscriptionInvoice)
def send_invoice_email(sender, instance, created, **kwargs):
    """Send invoice email when an invoice is created"""
    if created:
        from apps.subscriptionapp.services.invoice_service import InvoiceService

        # Send invoice email
        InvoiceService.send_invoice_email(instance.id)
