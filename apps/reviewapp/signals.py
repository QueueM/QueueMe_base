from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.reviewapp.models import ServiceReview, ShopReview, SpecialistReview
from apps.reviewapp.services.rating_service import RatingService


@receiver(post_save, sender=ShopReview)
def update_shop_metrics(sender, instance, created, **kwargs):
    """Update shop metrics when a review is saved"""
    if instance.status == "approved":
        RatingService.update_entity_metrics("shopapp.Shop", instance.shop_id)


@receiver(post_save, sender=SpecialistReview)
def update_specialist_metrics(sender, instance, created, **kwargs):
    """Update specialist metrics when a review is saved"""
    if instance.status == "approved":
        RatingService.update_entity_metrics(
            "specialistsapp.Specialist", instance.specialist_id
        )


@receiver(post_save, sender=ServiceReview)
def update_service_metrics(sender, instance, created, **kwargs):
    """Update service metrics when a review is saved"""
    if instance.status == "approved":
        RatingService.update_entity_metrics("serviceapp.Service", instance.service_id)


@receiver(post_delete, sender=ShopReview)
def update_shop_metrics_on_delete(sender, instance, **kwargs):
    """Update shop metrics when a review is deleted"""
    RatingService.update_entity_metrics("shopapp.Shop", instance.shop_id)


@receiver(post_delete, sender=SpecialistReview)
def update_specialist_metrics_on_delete(sender, instance, **kwargs):
    """Update specialist metrics when a review is deleted"""
    RatingService.update_entity_metrics(
        "specialistsapp.Specialist", instance.specialist_id
    )


@receiver(post_delete, sender=ServiceReview)
def update_service_metrics_on_delete(sender, instance, **kwargs):
    """Update service metrics when a review is deleted"""
    RatingService.update_entity_metrics("serviceapp.Service", instance.service_id)
