# apps/discountapp/signals.py
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.discountapp.models import Coupon, CouponUsage, PromotionalCampaign, ServiceDiscount


@receiver(pre_save, sender=ServiceDiscount)
def update_service_discount_status(sender, instance, **kwargs):
    """
    Update status of ServiceDiscount based on current date and usage before saving
    """
    # Get current time
    now = timezone.now()

    # Update status based on dates and usage
    if instance.start_date <= now <= instance.end_date:
        if instance.usage_limit > 0 and instance.used_count >= instance.usage_limit:
            instance.status = "expired"
        else:
            instance.status = "active"
    elif now < instance.start_date:
        instance.status = "scheduled"
    elif now > instance.end_date:
        instance.status = "expired"


@receiver(pre_save, sender=Coupon)
def update_coupon_status(sender, instance, **kwargs):
    """
    Update status of Coupon based on current date and usage before saving
    """
    # Get current time
    now = timezone.now()

    # Update status based on dates and usage
    if instance.start_date <= now <= instance.end_date:
        if instance.usage_limit > 0 and instance.used_count >= instance.usage_limit:
            instance.status = "expired"
        else:
            instance.status = "active"
    elif now < instance.start_date:
        instance.status = "scheduled"
    elif now > instance.end_date:
        instance.status = "expired"


@receiver(post_save, sender=CouponUsage)
def increment_coupon_usage(sender, instance, created, **kwargs):
    """
    Increment coupon usage count when a new usage is recorded
    """
    if created:
        coupon = instance.coupon

        # Use the model's increment_usage method which handles status updates
        coupon.increment_usage()


@receiver(m2m_changed, sender=PromotionalCampaign.coupons.through)
def update_coupon_campaign_dates(sender, instance, action, pk_set, **kwargs):
    """
    When coupons are added to a campaign, update their dates if needed
    """
    if action == "post_add" and pk_set and isinstance(instance, PromotionalCampaign):
        # Get coupons that were added
        coupons = Coupon.objects.filter(pk__in=pk_set)

        for coupon in coupons:
            # Update coupon dates if campaign dates are more restrictive
            updated = False

            if coupon.start_date < instance.start_date:
                coupon.start_date = instance.start_date
                updated = True

            if coupon.end_date > instance.end_date:
                coupon.end_date = instance.end_date
                updated = True

            if updated:
                coupon.save()


@receiver(m2m_changed, sender=PromotionalCampaign.service_discounts.through)
def update_discount_campaign_dates(sender, instance, action, pk_set, **kwargs):
    """
    When discounts are added to a campaign, update their dates if needed
    """
    if action == "post_add" and pk_set and isinstance(instance, PromotionalCampaign):
        # Get discounts that were added
        discounts = ServiceDiscount.objects.filter(pk__in=pk_set)

        for discount in discounts:
            # Update discount dates if campaign dates are more restrictive
            updated = False

            if discount.start_date < instance.start_date:
                discount.start_date = instance.start_date
                updated = True

            if discount.end_date > instance.end_date:
                discount.end_date = instance.end_date
                updated = True

            if updated:
                discount.save()
