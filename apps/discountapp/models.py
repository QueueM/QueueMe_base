# apps/discountapp/models.py
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.categoriesapp.models import Category
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class Discount(models.Model):
    """Base abstract discount model"""

    TYPE_CHOICES = (
        ("percentage", _("Percentage")),
        ("fixed", _("Fixed Amount")),
    )

    STATUS_CHOICES = (
        ("active", _("Active")),
        ("scheduled", _("Scheduled")),
        ("expired", _("Expired")),
        ("paused", _("Paused")),
        ("cancelled", _("Cancelled")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    discount_type = models.CharField(_("Discount Type"), max_length=10, choices=TYPE_CHOICES)
    value = models.DecimalField(
        _("Value"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Percentage or fixed amount value"),
    )
    max_discount_amount = models.DecimalField(
        _("Maximum Discount Amount"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Maximum discount amount for percentage discounts"),
    )
    min_purchase_amount = models.DecimalField(
        _("Minimum Purchase Amount"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Minimum purchase amount required to apply discount"),
    )
    start_date = models.DateTimeField(_("Start Date"))
    end_date = models.DateTimeField(_("End Date"))
    usage_limit = models.PositiveIntegerField(
        _("Usage Limit"), default=0, help_text=_("0 means unlimited")
    )
    used_count = models.PositiveIntegerField(_("Used Count"), default=0)
    status = models.CharField(
        _("Status"), max_length=10, choices=STATUS_CHOICES, default="scheduled"
    )
    is_combinable = models.BooleanField(
        _("Combinable"),
        default=False,
        help_text=_("Whether this discount can be combined with other discounts"),
    )
    priority = models.PositiveIntegerField(
        _("Priority"),
        default=0,
        help_text=_("Higher priority discounts are applied first"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="%(class)s_discounts",
        verbose_name=_("Shop"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-priority", "start_date"]

    def clean(self):
        """Validate model fields"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_("End date must be after start date"))

        if self.discount_type == "percentage" and (self.value < 0 or self.value > 100):
            raise ValidationError(_("Percentage discount must be between 0 and 100"))

        if self.discount_type == "fixed" and self.value < 0:
            raise ValidationError(_("Fixed discount cannot be negative"))

    def save(self, *args, **kwargs):
        """Override save to set status based on dates"""
        now = timezone.now()

        if self.start_date <= now <= self.end_date:
            if self.usage_limit > 0 and self.used_count >= self.usage_limit:
                self.status = "expired"
            else:
                self.status = "active"
        elif now < self.start_date:
            self.status = "scheduled"
        elif now > self.end_date:
            self.status = "expired"

        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if discount is currently valid"""
        now = timezone.now()
        if self.status == "active" and self.start_date <= now <= self.end_date:
            if self.usage_limit == 0 or self.used_count < self.usage_limit:
                return True
        return False

    def calculate_discount_amount(self, base_amount):
        """Calculate discount amount based on the discount type and value"""
        if not self.is_valid() or base_amount < self.min_purchase_amount:
            return 0

        if self.discount_type == "percentage":
            discount = (base_amount * self.value) / 100
            if self.max_discount_amount:
                return min(discount, self.max_discount_amount)
            return discount
        else:  # fixed amount
            return min(self.value, base_amount)

    def increment_usage(self):
        """Increment the used count"""
        self.used_count += 1
        if self.usage_limit > 0 and self.used_count >= self.usage_limit:
            self.status = "expired"
        self.save(update_fields=["used_count", "status"])


class ServiceDiscount(Discount):
    """Discount for specific services"""

    services = models.ManyToManyField(
        Service, related_name="discounts", verbose_name=_("Services"), blank=True
    )
    categories = models.ManyToManyField(
        Category,
        related_name="discounts",
        verbose_name=_("Categories"),
        blank=True,
        help_text=_("Categories of services this discount applies to"),
    )
    apply_to_all_services = models.BooleanField(_("Apply to All Services"), default=False)

    class Meta:
        verbose_name = _("Service Discount")
        verbose_name_plural = _("Service Discounts")

    def __str__(self):
        return f"{self.name} - {self.value}{self.discount_type == 'percentage' and '%' or ' SAR'} ({self.shop.name})"


class Coupon(Discount):
    """Coupon code discount"""

    code = models.CharField(_("Code"), max_length=20, unique=True)
    is_single_use = models.BooleanField(_("Single Use"), default=False)
    requires_authentication = models.BooleanField(_("Requires Authentication"), default=True)
    is_referral = models.BooleanField(_("Referral Coupon"), default=False)
    referred_by = models.ForeignKey(
        "authapp.User",
        on_delete=models.SET_NULL,
        related_name="referred_coupons",
        verbose_name=_("Referred By"),
        null=True,
        blank=True,
    )
    services = models.ManyToManyField(
        Service, related_name="coupons", verbose_name=_("Services"), blank=True
    )
    categories = models.ManyToManyField(
        Category, related_name="coupons", verbose_name=_("Categories"), blank=True
    )
    apply_to_all_services = models.BooleanField(_("Apply to All Services"), default=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="coupons", verbose_name=_("Shop")
    )

    class Meta:
        verbose_name = _("Coupon")
        verbose_name_plural = _("Coupons")

    def __str__(self):
        return f"{self.code} - {self.value}{self.discount_type == 'percentage' and '%' or ' SAR'} ({self.shop.name})"


class CouponUsage(models.Model):
    """Track coupon usage by customers"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages",
        verbose_name=_("Coupon"),
    )
    customer = models.ForeignKey(
        "authapp.User",
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        verbose_name=_("Customer"),
    )
    used_at = models.DateTimeField(_("Used At"), auto_now_add=True)
    booking = models.ForeignKey(
        "bookingapp.Appointment",
        on_delete=models.SET_NULL,
        related_name="coupon_usages",
        verbose_name=_("Booking"),
        null=True,
        blank=True,
    )
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("Coupon Usage")
        verbose_name_plural = _("Coupon Usages")
        unique_together = ("coupon", "booking")

    def __str__(self):
        return f"{self.coupon.code} used by {self.customer.phone_number}"


class PromotionalCampaign(models.Model):
    """Marketing campaign that may contain multiple discounts/coupons"""

    TYPE_CHOICES = (
        ("holiday", _("Holiday")),
        ("seasonal", _("Seasonal")),
        ("flash_sale", _("Flash Sale")),
        ("product_launch", _("Product Launch")),
        ("loyalty", _("Loyalty Program")),
        ("referral", _("Referral Program")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    campaign_type = models.CharField(_("Campaign Type"), max_length=20, choices=TYPE_CHOICES)
    start_date = models.DateTimeField(_("Start Date"))
    end_date = models.DateTimeField(_("End Date"))
    is_active = models.BooleanField(_("Active"), default=True)
    coupons = models.ManyToManyField(
        Coupon, related_name="campaigns", verbose_name=_("Coupons"), blank=True
    )
    service_discounts = models.ManyToManyField(
        ServiceDiscount,
        related_name="campaigns",
        verbose_name=_("Service Discounts"),
        blank=True,
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="promotional_campaigns",
        verbose_name=_("Shop"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Promotional Campaign")
        verbose_name_plural = _("Promotional Campaigns")

    def __str__(self):
        return f"{self.name} ({self.shop.name})"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_("End date must be after start date"))

    def is_active_now(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date
