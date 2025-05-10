# apps/storiesapp/models.py
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.shopapp.models import Shop


class Story(models.Model):
    """
    Story model representing ephemeral content from shops that expires after 24 hours.
    Stories can be images or videos and are displayed to customers on home screen (if followed)
    or on shop screen.
    """

    STORY_TYPE_CHOICES = (
        ("image", _("Image")),
        ("video", _("Video")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="stories",
        verbose_name=_("Shop"),
    )
    story_type = models.CharField(
        _("Story Type"), max_length=10, choices=STORY_TYPE_CHOICES
    )
    media_url = models.URLField(_("Media URL"))
    thumbnail_url = models.URLField(_("Thumbnail URL"), null=True, blank=True)
    created_at = models.DateTimeField(
        _("Created At"), auto_now_add=True, editable=False
    )
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Story")
        verbose_name_plural = _("Stories")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.shop.name} - {self.get_story_type_display()} - {ts}"

    def save(self, *args, **kwargs):
        """Override save to set expiry time to 24h after creation"""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if story has expired"""
        return timezone.now() > self.expires_at if self.expires_at else False

    @property
    def time_left(self):
        """Get time left before expiry in seconds"""
        if self.expires_at:
            diff = self.expires_at - timezone.now()
            return max(0, diff.total_seconds())
        return 0

    @property
    def view_count(self):
        """Get number of views"""
        return self.views.count()


class StoryView(models.Model):
    """
    Record of a customer viewing a story.
    Used to track story engagement and to avoid showing the same story multiple times.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        related_name="views",
        verbose_name=_("Story"),
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="story_views",
        verbose_name=_("Customer"),
    )
    viewed_at = models.DateTimeField(_("Viewed At"), auto_now_add=True, editable=False)

    class Meta:
        verbose_name = _("Story View")
        verbose_name_plural = _("Story Views")
        unique_together = ("story", "customer")
        indexes = [
            models.Index(fields=["story", "customer"]),
            models.Index(fields=["viewed_at"]),
        ]

    def __str__(self):
        ts = self.viewed_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.customer.phone_number} - {self.story.shop.name} - {ts}"
