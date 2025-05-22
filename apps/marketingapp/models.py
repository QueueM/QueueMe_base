"""
Models for marketing app.

This module defines models for advertisements, campaigns,
ad views, clicks, and related analytics.
"""

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AdType(models.TextChoices):
    """Types of advertisements"""

    IMAGE = "image", "Image"
    VIDEO = "video", "Video"


class AdStatus(models.TextChoices):
    """Status choices for advertisements"""

    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending Approval"
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    REJECTED = "rejected", "Rejected"


class TargetingType(models.TextChoices):
    """Targeting types for advertisements"""

    LOCATION = "location", "Location Based"
    CATEGORY = "category", "Category Based"
    INTEREST = "interest", "Interest Based"
    ALL = "all", "All Users"


class AdPlan(models.Model):
    """
    Predefined plans for advertisements with fixed pricing
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # In SAR
    duration_days = models.PositiveIntegerField()
    max_impressions = models.PositiveIntegerField(default=0)  # 0 means unlimited
    max_clicks = models.PositiveIntegerField(default=0)  # 0 means unlimited
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.price} SAR"

    class Meta:
        ordering = ["price"]
        verbose_name = "Ad Plan"
        verbose_name_plural = "Ad Plans"


class Campaign(models.Model):
    """
    Advertising campaign model - groups related advertisements
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        "companiesapp.Company", on_delete=models.CASCADE, related_name="campaigns"
    )
    shop = models.ForeignKey(
        "shopapp.Shop", on_delete=models.CASCADE, related_name="campaigns"
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)  # In SAR
    budget_spent = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # In SAR
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.shop.name}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"


class Advertisement(models.Model):
    """
    Advertisement model for storing ad content and settings
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="advertisements",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Plan relation
    plan = models.ForeignKey(
        AdPlan,
        on_delete=models.SET_NULL,
        related_name="advertisements",
        null=True,
        blank=True,
    )

    # Content type
    ad_type = models.CharField(
        max_length=20, choices=AdType.choices, default=AdType.IMAGE
    )
    image = models.ImageField(upload_to="ads/images/", null=True, blank=True)
    video = models.FileField(upload_to="ads/videos/", null=True, blank=True)

    # Targeting
    targeting_type = models.CharField(
        max_length=20, choices=TargetingType.choices, default=TargetingType.ALL
    )
    target_cities = models.ManyToManyField(
        "geoapp.City", related_name="targeted_ads", blank=True
    )
    target_categories = models.ManyToManyField(
        "categoriesapp.Category", related_name="targeted_ads", blank=True
    )

    # Linked resources (can link to shop, service, or specialist)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    linked_object = GenericForeignKey("content_type", "object_id")

    # Financial
    cost_per_view = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.10
    )  # In SAR
    cost_per_click = models.DecimalField(
        max_digits=6, decimal_places=2, default=1.00
    )  # In SAR

    # Status and billing
    status = models.CharField(
        max_length=20, choices=AdStatus.choices, default=AdStatus.DRAFT
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # Total amount paid

    # Metrics
    impression_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(
        default=0
    )  # Tracked bookings from ad

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # User relation
    user = models.ForeignKey(
        "authapp.User",
        on_delete=models.CASCADE,
        related_name="advertisements",
        null=True,
    )

    def __str__(self):
        return self.title

    @property
    def click_through_rate(self):
        """Calculate the click-through rate (CTR) of the ad"""
        if self.impression_count == 0:
            return 0
        return (self.click_count / self.impression_count) * 100

    @property
    def cost_per_conversion(self):
        """Calculate the cost per conversion"""
        if self.conversion_count == 0:
            return 0
        return self.amount / self.conversion_count

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Advertisement"
        verbose_name_plural = "Advertisements"


class AdView(models.Model):
    """Model to track advertisement impressions/views"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ad = models.ForeignKey(
        "Advertisement",
        on_delete=models.CASCADE,
        related_name="views",
        null=True,  # Make nullable
        blank=True,
    )
    advertisement = models.ForeignKey(
        "Advertisement",
        on_delete=models.CASCADE,
        related_name="advertisement_views",
        null=True,
        blank=True,
        db_constraint=False,  # Prevents DB constraint errors
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    location = models.ForeignKey(
        "geoapp.Location", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return (
            f"View of {self.ad.title if self.ad else 'unknown ad'} at {self.viewed_at}"
        )

    def save(self, *args, **kwargs):
        # Ensure advertisement field matches ad field
        if self.ad and not self.advertisement:
            self.advertisement = self.ad
        elif self.advertisement and not self.ad:
            self.ad = self.advertisement
        super().save(*args, **kwargs)


class AdClick(models.Model):
    """Model to track advertisement clicks"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ad = models.ForeignKey(
        "Advertisement",
        on_delete=models.CASCADE,
        related_name="clicks",
        null=True,  # Make nullable
        blank=True,
    )
    advertisement = models.ForeignKey(
        "Advertisement",
        on_delete=models.CASCADE,
        related_name="advertisement_clicks",
        null=True,
        blank=True,
        db_constraint=False,  # Prevents DB constraint errors
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    clicked_at = models.DateTimeField(auto_now_add=True)
    location = models.ForeignKey(
        "geoapp.Location", on_delete=models.SET_NULL, null=True, blank=True
    )
    referrer = models.URLField(max_length=500, null=True, blank=True)
    led_to_booking = models.BooleanField(default=False)
    conversion_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )

    def __str__(self):
        return f"Click on {self.ad.title if self.ad else 'unknown ad'} at {self.clicked_at}"

    def save(self, *args, **kwargs):
        # Ensure advertisement field matches ad field
        if self.ad and not self.advertisement:
            self.advertisement = self.ad
        elif self.advertisement and not self.ad:
            self.ad = self.advertisement
        super().save(*args, **kwargs)


class AdPayment(models.Model):
    """
    Tracks payments for advertisements
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advertisement = models.ForeignKey(
        Advertisement, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # In SAR

    # Payment processing
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default="completed")

    # Billing details
    invoice_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Payment for {self.advertisement.title}"

    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "Ad Payment"
        verbose_name_plural = "Ad Payments"
