# apps/subscriptionapp/models.py
import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.payment.models import Transaction

from .constants import (
    FEATURE_CATEGORY_CHOICES,
    FEATURE_TIER_CHOICES,
    PERIOD_MONTHLY,
    STATUS_INITIATED,
    SUBSCRIPTION_PERIOD_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
)


class Plan(models.Model):
    """Subscription plan definition with features and pricing"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Plan Name"), max_length=100)
    name_ar = models.CharField(_("Plan Name (Arabic)"), max_length=100, blank=True)
    description = models.TextField(_("Description"))
    description_ar = models.TextField(_("Description (Arabic)"), blank=True)
    monthly_price = models.DecimalField(
        _("Monthly Price (SAR)"), max_digits=10, decimal_places=2
    )
    max_shops = models.PositiveIntegerField(_("Maximum Shops/Branches"), default=1)
    max_services_per_shop = models.PositiveIntegerField(
        _("Maximum Services per Shop"), default=10
    )
    max_specialists_per_shop = models.PositiveIntegerField(
        _("Maximum Specialists per Shop"), default=5
    )
    is_active = models.BooleanField(_("Active"), default=True)
    is_featured = models.BooleanField(_("Featured"), default=False)
    position = models.PositiveIntegerField(_("Display Position"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")
        ordering = ["position", "monthly_price"]

    def __str__(self):
        return f"{self.name} - {self.monthly_price} SAR/month"

    def get_price_for_period(self, period=PERIOD_MONTHLY):
        """Calculate price for a specific subscription period with discount"""
        from apps.subscriptionapp.utils.billing_utils import calculate_period_price

        return calculate_period_price(self.monthly_price, period)


class PlanFeature(models.Model):
    """Features included in a subscription plan"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="features", verbose_name=_("Plan")
    )
    name = models.CharField(_("Feature Name"), max_length=100)
    name_ar = models.CharField(_("Feature Name (Arabic)"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True)
    description_ar = models.TextField(_("Description (Arabic)"), blank=True)
    category = models.CharField(
        _("Category"), max_length=20, choices=FEATURE_CATEGORY_CHOICES
    )
    tier = models.CharField(_("Tier"), max_length=20, choices=FEATURE_TIER_CHOICES)
    value = models.CharField(_("Value/Limit"), max_length=50, blank=True)
    is_available = models.BooleanField(_("Available"), default=True)

    class Meta:
        verbose_name = _("Plan Feature")
        verbose_name_plural = _("Plan Features")
        ordering = ["category", "tier"]

    def __str__(self):
        return f"{self.plan.name} - {self.name}"


class Subscription(models.Model):
    """Company subscription to a plan"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Company"),
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
        verbose_name=_("Plan"),
        null=True,
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default=STATUS_INITIATED,
    )
    period = models.CharField(
        _("Period"),
        max_length=20,
        choices=SUBSCRIPTION_PERIOD_CHOICES,
        default=PERIOD_MONTHLY,
    )
    start_date = models.DateTimeField(_("Start Date"), null=True, blank=True)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)
    auto_renew = models.BooleanField(_("Auto Renew"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    canceled_at = models.DateTimeField(_("Canceled At"), null=True, blank=True)
    trial_end = models.DateTimeField(_("Trial End Date"), null=True, blank=True)
    current_period_start = models.DateTimeField(
        _("Current Period Start"), null=True, blank=True
    )
    current_period_end = models.DateTimeField(
        _("Current Period End"), null=True, blank=True
    )
    moyasar_id = models.CharField(
        _("Moyasar ID"), max_length=255, blank=True, null=True
    )

    # Cached plan details (to maintain historical data if plan changes)
    plan_name = models.CharField(_("Plan Name"), max_length=100, blank=True)
    max_shops = models.PositiveIntegerField(_("Maximum Shops/Branches"), default=1)
    max_services_per_shop = models.PositiveIntegerField(
        _("Maximum Services per Shop"), default=10
    )
    max_specialists_per_shop = models.PositiveIntegerField(
        _("Maximum Specialists per Shop"), default=5
    )

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["current_period_end"]),
            models.Index(fields=["company"]),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.plan_name if self.plan_name else self.plan.name}"

    def is_active(self):
        """Check if subscription is currently active"""
        return (
            self.status == "active"
            and self.current_period_end
            and self.current_period_end > timezone.now()
        )

    def days_remaining(self):
        """Calculate days remaining in current period"""
        if not self.current_period_end:
            return 0

        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)

    def is_in_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_end:
            return False

        return self.trial_end > timezone.now()


class SubscriptionInvoice(models.Model):
    """Invoice for subscription payment"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Subscription"),
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        related_name="subscription_invoices",
        verbose_name=_("Transaction"),
        null=True,
        blank=True,
    )
    invoice_number = models.CharField(_("Invoice Number"), max_length=50)
    amount = models.DecimalField(_("Amount (SAR)"), max_digits=10, decimal_places=2)
    status = models.CharField(_("Status"), max_length=20)
    period_start = models.DateTimeField(_("Period Start"))
    period_end = models.DateTimeField(_("Period End"))
    issued_date = models.DateTimeField(_("Issued Date"), auto_now_add=True)
    due_date = models.DateTimeField(_("Due Date"))
    paid_date = models.DateTimeField(_("Paid Date"), null=True, blank=True)

    class Meta:
        verbose_name = _("Subscription Invoice")
        verbose_name_plural = _("Subscription Invoices")
        ordering = ["-issued_date"]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.subscription}"


class FeatureUsage(models.Model):
    """Tracks usage of features with limits"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="feature_usage",
        verbose_name=_("Subscription"),
    )
    feature_category = models.CharField(
        _("Feature Category"), max_length=20, choices=FEATURE_CATEGORY_CHOICES
    )
    limit = models.PositiveIntegerField(_("Limit"))
    current_usage = models.PositiveIntegerField(_("Current Usage"), default=0)
    last_updated = models.DateTimeField(_("Last Updated"), auto_now=True)

    class Meta:
        verbose_name = _("Feature Usage")
        verbose_name_plural = _("Feature Usage")
        unique_together = ("subscription", "feature_category")

    def __str__(self):
        return f"{self.subscription} - {self.get_feature_category_display()}: {self.current_usage}/{self.limit}"

    def is_limit_reached(self):
        """Check if usage limit is reached"""
        return self.current_usage >= self.limit


class SubscriptionLog(models.Model):
    """Log of subscription events for audit trail"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("Subscription"),
    )
    action = models.CharField(_("Action"), max_length=50)
    status_before = models.CharField(
        _("Status Before"), max_length=20, blank=True, null=True
    )
    status_after = models.CharField(
        _("Status After"), max_length=20, blank=True, null=True
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="subscription_actions",
        verbose_name=_("Performed By"),
        null=True,
        blank=True,
    )
    metadata = models.JSONField(_("Metadata"), default=dict)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Subscription Log")
        verbose_name_plural = _("Subscription Logs")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subscription} - {self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
