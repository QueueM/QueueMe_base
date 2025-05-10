import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User


class BaseReview(models.Model):
    """Abstract base class for all review types"""

    REVIEW_STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_("Title"), max_length=255)
    rating = models.PositiveSmallIntegerField(
        _("Rating"), validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    content = models.TextField(_("Review Content"))
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="%(class)s_reviews",
        verbose_name=_("User"),
        null=True,
    )
    city = models.CharField(_("City"), max_length=100, blank=True)
    status = models.CharField(
        _("Status"), max_length=20, choices=REVIEW_STATUS_CHOICES, default="approved"
    )
    is_verified_purchase = models.BooleanField(_("Verified Purchase"), default=False)
    moderation_comment = models.TextField(_("Moderation Comment"), blank=True)
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="moderated_%(class)s_reviews",
        verbose_name=_("Moderated By"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.phone_number if self.user else 'Unknown'} - {self.rating} stars - {self.created_at.strftime('%Y-%m-%d')}"


class ShopReview(BaseReview):
    """Customer review for a shop"""

    shop = models.ForeignKey(
        "shopapp.Shop",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Shop"),
    )
    related_booking = models.ForeignKey(
        "bookingapp.Appointment",
        on_delete=models.SET_NULL,
        related_name="shop_reviews",
        verbose_name=_("Related Booking"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Shop Review")
        verbose_name_plural = _("Shop Reviews")
        unique_together = ("user", "shop", "related_booking")
        indexes = [
            models.Index(fields=["shop", "created_at"]),
            models.Index(fields=["shop", "rating"]),
            models.Index(fields=["user", "shop"]),
        ]


class SpecialistReview(BaseReview):
    """Customer review for a specialist"""

    specialist = models.ForeignKey(
        "specialistsapp.Specialist",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Specialist"),
    )
    related_booking = models.ForeignKey(
        "bookingapp.Appointment",
        on_delete=models.SET_NULL,
        related_name="specialist_reviews",
        verbose_name=_("Related Booking"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Specialist Review")
        verbose_name_plural = _("Specialist Reviews")
        unique_together = ("user", "specialist", "related_booking")
        indexes = [
            models.Index(fields=["specialist", "created_at"]),
            models.Index(fields=["specialist", "rating"]),
            models.Index(fields=["user", "specialist"]),
        ]


class ServiceReview(BaseReview):
    """Customer review for a service"""

    service = models.ForeignKey(
        "serviceapp.Service",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Service"),
    )
    related_booking = models.ForeignKey(
        "bookingapp.Appointment",
        on_delete=models.SET_NULL,
        related_name="service_reviews",
        verbose_name=_("Related Booking"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Service Review")
        verbose_name_plural = _("Service Reviews")
        unique_together = ("user", "service", "related_booking")
        indexes = [
            models.Index(fields=["service", "created_at"]),
            models.Index(fields=["service", "rating"]),
            models.Index(fields=["user", "service"]),
        ]


class PlatformReview(BaseReview):
    """Shop review for the Queue Me platform"""

    company = models.ForeignKey(
        "companiesapp.Company",
        on_delete=models.CASCADE,
        related_name="platform_reviews",
        verbose_name=_("Company"),
    )
    category = models.CharField(_("Review Category"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Platform Review")
        verbose_name_plural = _("Platform Reviews")
        unique_together = ("company", "created_at")
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["rating"]),
        ]


class ReviewMedia(models.Model):
    """Media attached to a review"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic foreign key to link to any review type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    review = GenericForeignKey("content_type", "object_id")

    media_file = models.FileField(_("Media File"), upload_to="reviews/media/%Y/%m/%d/")
    media_type = models.CharField(
        _("Media Type"),
        max_length=10,
        choices=(
            ("image", _("Image")),
            ("video", _("Video")),
        ),
        default="image",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Review Media")
        verbose_name_plural = _("Review Media")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"Media for {self.content_type.model} review - {self.created_at.strftime('%Y-%m-%d')}"


class ReviewHelpfulness(models.Model):
    """Track if users found a review helpful"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic foreign key to link to any review type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    review = GenericForeignKey("content_type", "object_id")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="review_votes",
        verbose_name=_("User"),
    )
    is_helpful = models.BooleanField(_("Is Helpful"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Review Helpfulness")
        verbose_name_plural = _("Review Helpfulness")
        unique_together = ("content_type", "object_id", "user")

    def __str__(self):
        helpful_text = "helpful" if self.is_helpful else "not helpful"
        return f"{self.user.phone_number} found review {helpful_text}"


class ReviewReport(models.Model):
    """Report inappropriate reviews"""

    REPORT_REASON_CHOICES = (
        ("inappropriate", _("Inappropriate Content")),
        ("spam", _("Spam")),
        ("not_relevant", _("Not Relevant")),
        ("fake", _("Fake Review")),
        ("other", _("Other")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic foreign key to link to any review type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    review = GenericForeignKey("content_type", "object_id")

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="review_reports",
        verbose_name=_("Reporter"),
    )
    reason = models.CharField(_("Reason"), max_length=20, choices=REPORT_REASON_CHOICES)
    details = models.TextField(_("Details"), blank=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=(
            ("pending", _("Pending")),
            ("reviewed", _("Reviewed")),
            ("resolved", _("Resolved")),
            ("rejected", _("Rejected")),
        ),
        default="pending",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Review Report")
        verbose_name_plural = _("Review Reports")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Report by {self.reporter.phone_number} for {self.get_reason_display()}"


class ReviewMetric(models.Model):
    """Aggregate metrics for reviewable entities"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic foreign key to link to any reviewable entity (shop, specialist, service)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    entity = GenericForeignKey("content_type", "object_id")

    avg_rating = models.DecimalField(
        _("Average Rating"), max_digits=3, decimal_places=2
    )
    weighted_rating = models.DecimalField(
        _("Weighted Rating"), max_digits=3, decimal_places=2
    )
    review_count = models.PositiveIntegerField(_("Review Count"), default=0)
    rating_distribution = models.JSONField(_("Rating Distribution"), default=dict)
    last_reviewed_at = models.DateTimeField(
        _("Last Reviewed At"), null=True, blank=True
    )
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Review Metric")
        verbose_name_plural = _("Review Metrics")
        unique_together = ("content_type", "object_id")

    def __str__(self):
        return f"Metrics for {self.content_type.model} (ID: {self.object_id})"


Review = ServiceReview
