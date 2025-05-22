from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.bookingapp.models import Appointment
from apps.queueapp.models import QueueTicket
from apps.reportanalyticsapp.tasks import (
    detect_anomalies,
    update_shop_analytics,
    update_specialist_analytics,
)

# Import the specific review models instead of a generic Review
from apps.reviewapp.models import ServiceReview, ShopReview, SpecialistReview


@receiver(post_save, sender=Appointment)
def appointment_saved(sender, instance, created, **kwargs):
    """Update analytics when appointment is saved"""
    # Get date - convert timezone-aware datetime to date
    appointment_date = instance.start_time.date()

    # Update shop analytics
    update_shop_analytics.delay(
        shop_id=str(instance.shop.id), date=appointment_date.isoformat()
    )

    # Update specialist analytics if specialist is assigned
    if instance.specialist:
        update_specialist_analytics.delay(
            specialist_id=str(instance.specialist.id), date=appointment_date.isoformat()
        )

    # For completed or cancelled appointments, check for anomalies
    if instance.status in ["completed", "cancelled", "no_show"]:
        detect_anomalies.delay(
            entity_type="shop",
            entity_id=str(instance.shop.id),
            metric_type="booking_volume",
            reference_date=appointment_date.isoformat(),
        )


@receiver(post_save, sender=QueueTicket)
def queue_ticket_saved(sender, instance, created, **kwargs):
    """Update analytics when queue ticket is saved"""
    # Only process tickets that have been completed or cancelled
    if instance.status in ["served", "cancelled", "skipped"]:
        # Get date
        ticket_date = instance.join_time.date()

        # Update shop analytics
        update_shop_analytics.delay(
            shop_id=str(instance.queue.shop.id), date=ticket_date.isoformat()
        )

        # Update specialist analytics if specialist is assigned
        if instance.specialist:
            update_specialist_analytics.delay(
                specialist_id=str(instance.specialist.id), date=ticket_date.isoformat()
            )

        # Check for wait time anomalies
        if instance.status == "served" and instance.actual_wait_time:
            detect_anomalies.delay(
                entity_type="shop",
                entity_id=str(instance.queue.shop.id),
                metric_type="wait_time",
                reference_date=ticket_date.isoformat(),
            )


# Register signals for each review type
@receiver(post_save, sender=ShopReview)
def shop_review_saved(sender, instance, created, **kwargs):
    """Update analytics when a shop review is saved"""
    if created:
        review_date = instance.created_at.date()

        # Update shop analytics
        update_shop_analytics.delay(
            shop_id=str(instance.shop.id), date=review_date.isoformat()
        )

        # Check for rating anomalies
        detect_anomalies.delay(
            entity_type="shop",
            entity_id=str(instance.shop.id),
            metric_type="rating",
            reference_date=review_date.isoformat(),
        )


@receiver(post_save, sender=SpecialistReview)
def specialist_review_saved(sender, instance, created, **kwargs):
    """Update analytics when a specialist review is saved"""
    if created:
        review_date = instance.created_at.date()

        # Update specialist analytics
        update_specialist_analytics.delay(
            specialist_id=str(instance.specialist.id), date=review_date.isoformat()
        )

        # Check for rating anomalies
        detect_anomalies.delay(
            entity_type="specialist",
            entity_id=str(instance.specialist.id),
            metric_type="rating",
            reference_date=review_date.isoformat(),
        )


@receiver(post_save, sender=ServiceReview)
def service_review_saved(sender, instance, created, **kwargs):
    """Update analytics when a service review is saved"""
    if created:
        review_date = instance.created_at.date()

        # Get the shop from the service
        shop_id = instance.service.shop_id

        # Update shop analytics
        update_shop_analytics.delay(shop_id=str(shop_id), date=review_date.isoformat())

        # Check for rating anomalies
        detect_anomalies.delay(
            entity_type="service",
            entity_id=str(instance.service.id),
            metric_type="rating",
            reference_date=review_date.isoformat(),
        )
