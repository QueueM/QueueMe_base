# apps/discountapp/tasks.py
from celery import shared_task
from django.utils import timezone

from apps.discountapp.models import Coupon, PromotionalCampaign, ServiceDiscount
from apps.discountapp.services.discount_service import DiscountService
from apps.notificationsapp.services.notification_service import NotificationService


@shared_task
def update_discount_statuses():
    """
    Task to update status of all discounts and coupons based on current date and usage
    """
    # Call the service method
    DiscountService.update_discount_statuses()

    return "Discount statuses updated"


@shared_task
def expire_ended_campaigns():
    """
    Task to mark promotional campaigns as inactive if their end date has passed
    """
    now = timezone.now()

    # Find campaigns that are active but ended
    ended_campaigns = PromotionalCampaign.objects.filter(
        is_active=True, end_date__lt=now
    )

    # Mark them as inactive
    count = ended_campaigns.update(is_active=False)

    return f"{count} campaigns marked as inactive"


@shared_task
def send_discount_expiry_notifications(days_before=3):
    """
    Task to send notifications to shop managers about discounts or coupons
    that will expire soon
    """
    now = timezone.now()
    expiry_threshold = now + timezone.timedelta(days=days_before)

    # Find discounts and coupons expiring soon
    expiring_discounts = ServiceDiscount.objects.filter(
        status="active", end_date__gt=now, end_date__lte=expiry_threshold
    )

    expiring_coupons = Coupon.objects.filter(
        status="active", end_date__gt=now, end_date__lte=expiry_threshold
    )

    # Group by shop to send consolidated notifications
    shop_discounts = {}

    for discount in expiring_discounts:
        if discount.shop_id not in shop_discounts:
            shop_discounts[discount.shop_id] = {
                "shop": discount.shop,
                "discounts": [],
                "coupons": [],
            }
        shop_discounts[discount.shop_id]["discounts"].append(discount)

    for coupon in expiring_coupons:
        if coupon.shop_id not in shop_discounts:
            shop_discounts[coupon.shop_id] = {
                "shop": coupon.shop,
                "discounts": [],
                "coupons": [],
            }
        shop_discounts[coupon.shop_id]["coupons"].append(coupon)

    # Send notifications to shop managers
    notifications_sent = 0

    for shop_id, data in shop_discounts.items():
        shop = data["shop"]

        # Skip if no expiring items
        if not data["discounts"] and not data["coupons"]:
            continue

        # Get shop manager
        manager = shop.manager

        if manager:
            # Prepare notification data
            expiring_items = []

            for discount in data["discounts"]:
                expiring_items.append(
                    {
                        "type": "discount",
                        "name": discount.name,
                        "end_date": discount.end_date.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            for coupon in data["coupons"]:
                expiring_items.append(
                    {
                        "type": "coupon",
                        "name": coupon.name,
                        "code": coupon.code,
                        "end_date": coupon.end_date.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            # Send notification
            NotificationService.send_notification(
                user_id=manager.id,
                notification_type="discount_expiry",
                data={
                    "shop_name": shop.name,
                    "days_before": days_before,
                    "expiring_items": expiring_items,
                },
                channels=["email", "push", "in_app"],
            )

            notifications_sent += 1

    return f"Sent {notifications_sent} discount expiry notifications"


@shared_task
def cleanup_expired_discounts(days_threshold=30):
    """
    Task to clean up long-expired discounts and coupons that are no longer needed
    This is an optional maintenance task (discounts should normally be kept for record)
    """
    now = timezone.now()
    cleanup_threshold = now - timezone.timedelta(days=days_threshold)

    # Find long-expired discounts
    old_discounts = ServiceDiscount.objects.filter(
        status="expired", end_date__lt=cleanup_threshold
    )

    # Find long-expired coupons
    old_coupons = Coupon.objects.filter(
        status="expired", end_date__lt=cleanup_threshold
    )

    # Delete only if configured (could be skipped or archived instead)
    discount_count = old_discounts.count()
    coupon_count = old_coupons.count()

    # Actual deletion is commented out as it's generally better to keep records
    # old_discounts.delete()
    # old_coupons.delete()

    return f"Found {discount_count} old discounts and {coupon_count} old coupons"
