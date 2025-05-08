from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.specialistsapp.models import Specialist

from .models import Shop, ShopSettings, ShopVerification


@receiver(post_save, sender=Shop)
def create_shop_settings(sender, instance, created, **kwargs):
    """Create shop settings when a new shop is created"""
    if created:
        ShopSettings.objects.create(shop=instance)


@receiver(post_save, sender=ShopVerification)
def handle_verification_approval(sender, instance, **kwargs):
    """Update shop verification status when verification is approved"""
    if instance.status == "approved":
        shop = instance.shop
        shop.is_verified = True
        shop.verification_date = timezone.now()
        shop.save(update_fields=["is_verified", "verification_date"])

        # Also verify all specialists in this shop
        Specialist.objects.filter(employee__shop=shop).update(is_verified=True)
