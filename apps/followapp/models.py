import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.shopapp.models import Shop


class Follow(models.Model):
    """
    Represents a customer following a shop to receive updates and content.
    This relationship drives the personalized content in the following feeds.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follows",
        verbose_name=_("Customer"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="follow_relationships",
        verbose_name=_("Shop"),
    )
    created_at = models.DateTimeField(_("Followed At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    notification_preference = models.BooleanField(
        _("Receive Notifications"),
        default=True,
        help_text=_("Whether to receive notifications about shop updates"),
    )

    class Meta:
        verbose_name = _("Follow")
        verbose_name_plural = _("Follows")
        unique_together = ("customer", "shop")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer"]),
            models.Index(fields=["shop"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.customer.phone_number} → {self.shop.name}"


class FollowStats(models.Model):
    """
    Pre-calculated statistics about shop followers for quick access.
    Maintains counts and trends to avoid expensive real-time calculations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="follow_stats",
        verbose_name=_("Shop"),
    )
    follower_count = models.PositiveIntegerField(_("Follower Count"), default=0)
    weekly_growth = models.IntegerField(_("Weekly Growth"), default=0)
    monthly_growth = models.IntegerField(_("Monthly Growth"), default=0)
    last_calculated = models.DateTimeField(_("Last Calculated"), default=timezone.now)

    class Meta:
        verbose_name = _("Follow Statistics")
        verbose_name_plural = _("Follow Statistics")

    def __str__(self):
        return f"Stats for {self.shop.name} - {self.follower_count} followers"


class FollowEvent(models.Model):
    """
    Log of follow/unfollow events for analytics and trend calculation.
    Provides historical data for analyzing shop popularity trends.
    """

    EVENT_TYPES = (
        ("follow", _("Follow")),
        ("unfollow", _("Unfollow")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follow_events",
        verbose_name=_("Customer"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="follow_events",
        verbose_name=_("Shop"),
    )
    event_type = models.CharField(_("Event Type"), max_length=10, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    source = models.CharField(
        _("Source"),
        max_length=50,
        null=True,
        blank=True,
        help_text=_(
            'Source of the follow/unfollow action (e.g., "shop_profile", "reel", "story")'
        ),
    )

    class Meta:
        verbose_name = _("Follow Event")
        verbose_name_plural = _("Follow Events")
        indexes = [
            models.Index(fields=["shop", "event_type", "timestamp"]),
            models.Index(fields=["customer", "event_type", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()}: {self.customer.phone_number} - {self.shop.name}"
