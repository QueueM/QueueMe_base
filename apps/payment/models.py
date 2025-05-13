import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User

from .constants import PAYMENT_TYPES, REFUND_STATUSES, TRANSACTION_STATUSES, TRANSACTION_TYPES


class PaymentStatus(models.TextChoices):
    """Payment transaction status choices"""

    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    REFUNDED = "refunded", _("Refunded")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")
    CANCELLED = "cancelled", _("Cancelled")


class RefundStatus(models.TextChoices):
    """Refund status choices"""

    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")


class PaymentWalletType(models.TextChoices):
    """
    Types of payment wallets for different payment purposes
    """

    SUBSCRIPTION = "subscription", _("Subscription")  # For company subscription payments
    ADS = "ads", _("Advertising")  # For company advertising payments
    MERCHANT = "merchant", _("Merchant")  # For customer service payments (default)


class PaymentMethod(models.Model):
    """Saved payment method for a customer"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payment_methods",
        verbose_name=_("User"),
    )
    type = models.CharField(_("Type"), max_length=20, choices=PAYMENT_TYPES)
    token = models.CharField(_("Token"), max_length=255)
    last_digits = models.CharField(_("Last Digits"), max_length=4, null=True, blank=True)
    expiry_month = models.CharField(_("Expiry Month"), max_length=2, null=True, blank=True)
    expiry_year = models.CharField(_("Expiry Year"), max_length=4, null=True, blank=True)
    card_brand = models.CharField(_("Card Brand"), max_length=20, null=True, blank=True)
    is_default = models.BooleanField(_("Default"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        unique_together = ("user", "token")
        indexes = [
            models.Index(fields=["user", "is_default"]),
            models.Index(fields=["token"]),
        ]
        app_label = "payment"

    def __str__(self):
        if self.type == "card" and self.last_digits:
            return f"{self.get_type_display()} - **** **** **** {self.last_digits}"
        return self.get_type_display()

    def save(self, *args, **kwargs):
        # If this is the default payment method, remove default from other methods
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).exclude(
                id=self.id
            ).update(is_default=False)

        # If this is the user's first payment method, make it default
        if not self.id and not PaymentMethod.objects.filter(user=self.user).exists():
            self.is_default = True

        super().save(*args, **kwargs)


class Transaction(models.Model):
    """
    Main payment transaction model that can be linked to various entities
    (bookings, subscriptions, etc.)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="SAR")
    description = models.CharField(max_length=255, default="Payment transaction")
    status = models.CharField(max_length=20, choices=[(s.value, s.value) for s in PaymentStatus])
    payment_method = models.ForeignKey(
        PaymentMethod,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="base_transactions",
    )
    wallet_type = models.CharField(
        max_length=20,
        choices=[(t.value, t.value) for t in PaymentWalletType],
        default=PaymentWalletType.MERCHANT.value,
    )
    provider_transaction_id = models.CharField(max_length=255, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payment"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["wallet_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["provider_transaction_id"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "wallet_type"]),
        ]
        ordering = ["-created_at"]
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")

    @property
    def amount_halalas(self):
        """Convert SAR to halalas (1 SAR = 100 halalas)"""
        return int(self.amount * 100)

    def __str__(self):
        return f"{self.provider_transaction_id}: {self.amount} SAR ({self.status})"


class RefundRequest(models.Model):
    """
    Records refund requests and their status
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="refund_requests"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=50)
    provider_refund_id = models.CharField(max_length=255, null=True, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    @property
    def amount_halalas(self):
        """Convert SAR to halalas (1 SAR = 100 halalas)"""
        return int(self.amount * 100)

    def __str__(self):
        return f"Refund {self.amount} SAR for {self.transaction.provider_transaction_id} ({self.status})"


class Refund(models.Model):
    """Refund record for a transaction"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="refunds",
        verbose_name=_("Transaction"),
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=[(s.value, s.value) for s in RefundStatus])
    provider_refund_id = models.CharField(max_length=255, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payment"
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["provider_refund_id"]),
        ]
        ordering = ["-created_at"]
        verbose_name = _("Refund")
        verbose_name_plural = _("Refunds")

    def __str__(self):
        return f"{self.transaction} - {self.amount} SAR - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Calculate halalas if not provided (1 SAR = 100 Halalas)
        if not hasattr(self, "amount_halalas") and self.amount:
            self.amount_halalas = int(self.amount * 100)
        super().save(*args, **kwargs)


class PaymentLog(models.Model):
    """Log of payment-related actions for auditing and debugging"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("Transaction"),
        null=True,
        blank=True,
    )
    refund = models.ForeignKey(
        Refund,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("Refund"),
        null=True,
        blank=True,
    )
    action = models.CharField(_("Action"), max_length=50)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="payment_logs",
        verbose_name=_("User"),
        null=True,
        blank=True,
    )
    details = models.JSONField(_("Details"), default=dict)
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Payment Log")
        verbose_name_plural = _("Payment Logs")
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class FraudDetectionRule(models.Model):
    """Rules for the fraud detection system"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    rule_type = models.CharField(_("Rule Type"), max_length=50)
    parameters = models.JSONField(_("Parameters"), default=dict)
    risk_score = models.DecimalField(_("Risk Score"), max_digits=5, decimal_places=2)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Fraud Detection Rule")
        verbose_name_plural = _("Fraud Detection Rules")

    def __str__(self):
        return self.name


class PaymentTransaction(models.Model):
    """
    Payment transaction model
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        "companiesapp.Company",
        on_delete=models.SET_NULL,
        related_name="payment_transactions",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="SAR")
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    wallet_type = models.CharField(
        max_length=20,
        choices=PaymentWalletType.choices,
        default=PaymentWalletType.MERCHANT,
        help_text="The wallet used for this payment",
    )
    external_id = models.CharField(max_length=100, blank=True, null=True)
    idempotency_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    source_type = models.CharField(max_length=50, blank=True)
    source_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.ForeignKey(
        "PaymentMethod",
        on_delete=models.SET_NULL,
        related_name="payment_transactions",
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_response = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["wallet_type"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["created_at"]),
        ]
        app_label = "payment"
