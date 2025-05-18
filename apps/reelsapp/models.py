from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.categoriesapp.models import Category
from apps.packageapp.models import Package
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from core.storage import MediaStorage  # Storage for media files like videos
from utils.validators import validate_image_size, validate_video_size


# --------------------------------------------------------------------------- #
# Reel
# --------------------------------------------------------------------------- #
class Reel(models.Model):
    """Short video clip published by a shop."""

    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("published", _("Published")),
        ("archived", _("Archived")),
        ("removed", _("Removed")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="reels", verbose_name=_("Shop")
    )
    title = models.CharField(_("Title"), max_length=100)
    caption = models.TextField(_("Caption"), blank=True)
    video = models.FileField(
        _("Video"),
        upload_to="reels/videos/",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_video_size,
        ],
        help_text=_("Maximum file size: 50 MB. Formats: MP4, MOV, AVI."),
    )
    thumbnail = models.ImageField(
        _("Thumbnail"),
        upload_to="reels/thumbnails/",
        validators=[validate_image_size],
        blank=True,
        null=True,
        help_text=_("Thumbnail image for the reel."),
    )
    duration = models.PositiveIntegerField(_("Duration (seconds)"), default=0)
    status = models.CharField(_("Status"), max_length=10, choices=STATUS_CHOICES, default="draft")

    # Tags / relations
    categories = models.ManyToManyField(
        Category, related_name="reels", verbose_name=_("Categories"), blank=True
    )
    services = models.ManyToManyField(
        Service, related_name="reels", verbose_name=_("Related Services"), blank=True
    )
    packages = models.ManyToManyField(
        Package, related_name="reels", verbose_name=_("Related Packages"), blank=True
    )

    processing_status = models.CharField(_("Processing Status"), max_length=20, default="pending")
    view_count = models.PositiveIntegerField(_("View Count"), default=0)
    is_featured = models.BooleanField(_("Featured"), default=False)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    published_at = models.DateTimeField(_("Published At"), null=True, blank=True)

    city = models.CharField(_("City"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("Reel")
        verbose_name_plural = _("Reels")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "-created_at"]),
            models.Index(fields=["city", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def __str__(self) -> str:
        return f"{self.shop.name} – {self.title}"

    def save(self, *args, **kwargs) -> None:  # noqa: D401
        """Set `city` from the shop's location on first save."""
        if not self.city and self.shop and self.shop.location:
            self.city = self.shop.location.city
        super().save(*args, **kwargs)

    # Engagement metrics --------------------------------------------------- #
    def get_engagement_score(self) -> int:
        """Weighted engagement: likes + 2×comments + 3×shares."""
        return self.total_likes + (self.total_comments * 2) + (self.total_shares * 3)

    @property
    def total_likes(self) -> int:
        return self.likes.count()

    @property
    def total_comments(self) -> int:
        return self.comments.count()

    @property
    def total_shares(self) -> int:
        return self.shares.count()


# --------------------------------------------------------------------------- #
# Like
# --------------------------------------------------------------------------- #
class ReelLike(models.Model):
    """User "like" on a reel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="likes", verbose_name=_("Reel")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reel_likes",
        verbose_name=_("User"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Reel Like")
        verbose_name_plural = _("Reel Likes")
        unique_together = ("reel", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reel", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} liked {self.reel.title}"


# --------------------------------------------------------------------------- #
# Comment
# --------------------------------------------------------------------------- #
class ReelComment(models.Model):
    """User comment on a reel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="comments", verbose_name=_("Reel")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reel_comments",
        verbose_name=_("User"),
    )
    content = models.TextField(_("Content"))
    is_hidden = models.BooleanField(_("Hidden"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Reel Comment")
        verbose_name_plural = _("Reel Comments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reel", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} commented on {self.reel.title}"


# --------------------------------------------------------------------------- #
# Share
# --------------------------------------------------------------------------- #
class ReelShare(models.Model):
    """Record that a user shared a reel."""

    SHARE_TYPE_CHOICES = (
        ("in_app", _("In-App")),
        ("whatsapp", _("WhatsApp")),
        ("sms", _("SMS")),
        ("other", _("Other")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="shares", verbose_name=_("Reel")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reel_shares",
        verbose_name=_("User"),
    )
    share_type = models.CharField(
        _("Share Type"), max_length=10, choices=SHARE_TYPE_CHOICES, default="in_app"
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Reel Share")
        verbose_name_plural = _("Reel Shares")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reel", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} shared {self.reel.title} via {self.get_share_type_display()}"


# --------------------------------------------------------------------------- #
# View
# --------------------------------------------------------------------------- #
class ReelView(models.Model):
    """Single playback event (optionally anonymous)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="views", verbose_name=_("Reel")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reel_views",
        verbose_name=_("User"),
        null=True,
        blank=True,
    )
    device_id = models.CharField(_("Device ID"), max_length=255, blank=True, null=True)
    watch_duration = models.PositiveIntegerField(_("Watch Duration (seconds)"), default=0)
    watched_full = models.BooleanField(_("Watched Full"), default=False)
    ip_address = models.GenericIPAddressField(_("IP Address"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Reel View")
        verbose_name_plural = _("Reel Views")
        indexes = [
            models.Index(fields=["reel", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        identity = self.user or self.device_id or "Anonymous"
        return f"{identity} viewed {self.reel.title}"


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
class ReelReport(models.Model):
    """User report about a reel's content."""

    REPORT_REASON_CHOICES = (
        ("inappropriate", _("Inappropriate Content")),
        ("spam", _("Spam")),
        ("offensive", _("Offensive")),
        ("copyright", _("Copyright Violation")),
        ("other", _("Other")),
    )
    STATUS_CHOICES = (
        ("pending", _("Pending Review")),
        ("reviewed", _("Reviewed")),
        ("actioned", _("Actioned")),
        ("dismissed", _("Dismissed")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="reports", verbose_name=_("Reel")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reel_reports",
        verbose_name=_("User"),
    )
    reason = models.CharField(_("Reason"), max_length=20, choices=REPORT_REASON_CHOICES)
    description = models.TextField(_("Description"), blank=True)
    status = models.CharField(_("Status"), max_length=10, choices=STATUS_CHOICES, default="pending")
    admin_notes = models.TextField(_("Admin Notes"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Reel Report")
        verbose_name_plural = _("Reel Reports")
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["reel", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Report {self.reason} by {self.user} on {self.reel.title}"
