from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.shopapp.models import Shop
from apps.specialistsapp.constants import SPECIALIST_CACHE_KEY, SPECIALIST_TOP_RATED_CACHE_KEY
from apps.specialistsapp.models import PortfolioItem, Specialist, SpecialistService


@receiver(post_save, sender=Specialist)
def specialist_post_save(sender, instance, created, **kwargs):
    """Handle post save actions for Specialist model"""
    # Invalidate cache
    cache.delete(SPECIALIST_CACHE_KEY.format(id=instance.id))
    cache.delete_many(
        [
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=5),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=10),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id=instance.employee.shop.id, limit=5),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id=instance.employee.shop.id, limit=10),
        ]
    )

    # If created, notify shop managers
    if created:
        # Import here to avoid circular import
        from apps.notificationsapp.services.notification_service import NotificationService
        from apps.rolesapp.models import Role, UserRole

        # Get shop managers and owner
        shop = instance.employee.shop
        shop_manager_roles = Role.objects.filter(role_type="shop_manager", shop=shop)
        manager_user_ids = UserRole.objects.filter(role__in=shop_manager_roles).values_list(
            "user_id", flat=True
        )

        # Add company owner
        if shop.company and shop.company.owner:
            manager_user_ids = list(manager_user_ids) + [shop.company.owner.id]

        # Send notification to each manager
        specialist_name = f"{instance.employee.first_name} {instance.employee.last_name}"
        for user_id in manager_user_ids:
            NotificationService.send_notification(
                user_id=user_id,
                notification_type="new_specialist",
                data={
                    "specialist_id": str(instance.id),
                    "specialist_name": specialist_name,
                    "shop_name": shop.name,
                },
            )


@receiver(post_delete, sender=Specialist)
def specialist_post_delete(sender, instance, **kwargs):
    """Handle post delete actions for Specialist model"""
    # Invalidate cache
    cache.delete(SPECIALIST_CACHE_KEY.format(id=instance.id))
    cache.delete_many(
        [
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=5),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=10),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id=instance.employee.shop.id, limit=5),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id=instance.employee.shop.id, limit=10),
        ]
    )


@receiver(post_save, sender=Shop)
def shop_verification_post_save(sender, instance, **kwargs):
    """Handle post save actions for Shop model - verify specialists when shop is verified"""
    if instance.is_verified:
        # Get all specialists for this shop
        specialists = Specialist.objects.filter(employee__shop=instance, is_verified=False)

        # Mark them as verified
        if specialists.exists():
            specialists.update(
                is_verified=True,
                verified_at=instance.verification_date or timezone.now(),
            )


@receiver(post_save, sender=SpecialistService)
def specialist_service_post_save(sender, instance, **kwargs):
    """Handle post save actions for SpecialistService model"""
    # Invalidate cache
    cache.delete(SPECIALIST_CACHE_KEY.format(id=instance.specialist.id))
    cache.delete_many(
        [
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=5),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(shop_id="all", limit=10),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(
                shop_id=instance.specialist.employee.shop.id, limit=5
            ),
            SPECIALIST_TOP_RATED_CACHE_KEY.format(
                shop_id=instance.specialist.employee.shop.id, limit=10
            ),
        ]
    )


@receiver(post_save, sender=PortfolioItem)
def portfolio_item_post_save(sender, instance, **kwargs):
    """Handle post save actions for PortfolioItem model"""
    # Invalidate cache
    cache.delete(SPECIALIST_CACHE_KEY.format(id=instance.specialist.id))
