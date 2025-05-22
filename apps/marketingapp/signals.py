"""
Signal handlers for Marketing app.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AdClick, Advertisement, AdView, Campaign

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AdView)
def update_campaign_budget_on_view(sender, instance, created, **kwargs):
    """
    Update campaign budget when a view is recorded.
    """
    if created and instance.advertisement.campaign:
        try:
            campaign = instance.advertisement.campaign
            campaign.budget_spent += instance.advertisement.cost_per_view
            campaign.save(update_fields=["budget_spent"])

            logger.debug(
                f"Updated campaign budget for view: {campaign.id}, "
                f"new budget spent: {campaign.budget_spent}"
            )
        except Exception as e:
            logger.error(f"Error updating campaign budget for view: {str(e)}")


@receiver(post_save, sender=AdClick)
def update_campaign_budget_on_click(sender, instance, created, **kwargs):
    """
    Update campaign budget when a click is recorded.
    """
    if created and instance.advertisement.campaign:
        try:
            campaign = instance.advertisement.campaign
            campaign.budget_spent += instance.advertisement.cost_per_click
            campaign.save(update_fields=["budget_spent"])

            logger.debug(
                f"Updated campaign budget for click: {campaign.id}, "
                f"new budget spent: {campaign.budget_spent}"
            )
        except Exception as e:
            logger.error(f"Error updating campaign budget for click: {str(e)}")


@receiver(post_save, sender=Campaign)
def check_campaign_budget_limit(sender, instance, **kwargs):
    """
    Check if campaign has reached its budget limit and deactivate if needed.
    """
    if instance.is_active and instance.budget_spent >= instance.budget:
        try:
            instance.is_active = False
            instance.save(update_fields=["is_active"])

            # Deactivate all active ads in the campaign
            active_ads = Advertisement.objects.filter(
                campaign=instance, status="active"
            )

            for ad in active_ads:
                ad.status = "paused"
                ad.save(update_fields=["status"])

            logger.info(
                f"Campaign {instance.id} reached budget limit and was deactivated. "
                f"Budget: {instance.budget}, Spent: {instance.budget_spent}"
            )
        except Exception as e:
            logger.error(f"Error deactivating campaign on budget limit: {str(e)}")


@receiver(post_save, sender=Advertisement)
def update_campaign_status_on_ad_change(sender, instance, created, **kwargs):
    """
    Update campaign status when an ad is created or updated.
    """
    if instance.campaign:
        # Ensure campaign is active if it has active ads and is under budget
        try:
            campaign = instance.campaign

            # Check if campaign has active ads
            has_active_ads = Advertisement.objects.filter(
                campaign=campaign, status="active"
            ).exists()

            # Check if campaign is under budget
            is_under_budget = campaign.budget_spent < campaign.budget

            # Update campaign status if needed
            if has_active_ads and is_under_budget and not campaign.is_active:
                campaign.is_active = True
                campaign.save(update_fields=["is_active"])
                logger.info(
                    f"Campaign {campaign.id} activated due to active ads and budget available"
                )

        except Exception as e:
            logger.error(f"Error updating campaign status on ad change: {str(e)}")
