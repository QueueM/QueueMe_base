# apps/companiesapp/signals.py
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.shopapp.models import Shop
from apps.subscriptionapp.models import Subscription
from core.storage.s3_storage import S3Storage

from .models import Company, CompanyDocument, CompanySettings


@receiver(post_save, sender=Company)
def create_company_settings(sender, instance, created, **kwargs):
    """Create company settings when a company is created"""
    if created:
        CompanySettings.objects.get_or_create(company=instance)


@receiver(post_save, sender=Subscription)
def update_company_subscription_status(sender, instance, **kwargs):
    """Update company's subscription status when subscription changes"""
    try:
        company = instance.company

        # Update the cached subscription status and end date
        company.subscription_status = instance.status
        company.subscription_end_date = instance.end_date
        company.save(update_fields=["subscription_status", "subscription_end_date"])

        # If subscription became inactive, update shop status
        if instance.status != "active":
            from apps.subscriptionapp.services.subscription_service import SubscriptionService

            SubscriptionService.handle_inactive_subscription(company)
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error updating company subscription status: {str(e)}")


@receiver(post_save, sender=Shop)
@receiver(post_delete, sender=Shop)
def update_company_shop_count(sender, instance, **kwargs):
    """Update company's shop count when shops are added or removed"""
    try:
        company = instance.company
        company.update_counts()
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error updating company shop count: {str(e)}")


@receiver(post_delete, sender=CompanyDocument)
def delete_document_file(sender, instance, **kwargs):
    """Delete the actual document file when a CompanyDocument is deleted"""
    if instance.document:
        try:
            # Use S3 storage to delete the file
            s3_storage = S3Storage()
            s3_storage.delete_file(instance.document.url)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting company document file: {str(e)}")


@receiver(post_save, sender=CompanyDocument)
def handle_document_verification(sender, instance, created, **kwargs):
    """Handle document verification"""
    if not created and instance.is_verified and not instance.verified_at:
        # Document was just verified
        instance.verified_at = timezone.now()
        instance.save(update_fields=["verified_at"])

        # Send notification
        try:
            from apps.notificationsapp.services.notification_service import NotificationService

            NotificationService.send_notification(
                user_id=instance.company.owner.id,
                notification_type="document_verified",
                data={
                    "document_title": instance.title,
                    "company_name": instance.company.name,
                    "verified_at": instance.verified_at.isoformat(),
                },
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error sending document verification notification: {str(e)}")
