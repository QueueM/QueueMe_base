from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.shopapp.models import Shop
from apps.shopDashboardApp.models import DashboardLayout
from apps.shopDashboardApp.services.settings_service import SettingsService


@receiver(post_save, sender=Shop)
def create_dashboard_settings_for_shop(sender, instance, created, **kwargs):
    """Create default dashboard settings and layout when a shop is created"""
    if created:
        # Create default settings if not exists
        if not hasattr(instance, "dashboard_settings"):
            settings_service = SettingsService()
            settings_service.create_default_settings(instance.id)

        # Create default layout if not exists
        if not DashboardLayout.objects.filter(shop=instance, is_default=True).exists():
            settings_service = SettingsService()
            settings_service.create_default_layout(instance.id, instance.manager_id)


@receiver(post_save, sender=DashboardLayout)
def enforce_single_default_layout(sender, instance, created, **kwargs):
    """Ensure only one default layout per shop"""
    if instance.is_default:
        # Set all other layouts for this shop to non-default
        DashboardLayout.objects.filter(shop=instance.shop, is_default=True).exclude(
            pk=instance.pk
        ).update(is_default=False)
