import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User

from .constants import (
    PAYMENT_TYPES,
    REFUND_STATUSES,
    TRANSACTION_STATUSES,
    TRANSACTION_TYPES,
)


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
    last_digits = models.CharField(
        _("Last Digits"), max_length=4, null=True, blank=True
    )
    expiry_month = models.CharField(
        _("Expiry Month"), max_length=2, null=True, blank=True
    )
    expiry_year = models.CharField(
        _("Expiry Year"), max_length=4, null=True, blank=True
    )
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
    """Payment transaction record"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moyasar_id = models.CharField(
        _("Moyasar ID"), max_length=255, null=True, blank=True
    )
    amount = models.DecimalField(_("Amount (SAR)"), max_digits=10, decimal_places=2)
    amount_halalas = models.IntegerField(_("Amount (Halalas)"))
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name=_("User"),
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        related_name="transactions",
        verbose_name=_("Payment Method"),
        null=True,
        blank=True,
    )
    payment_type = models.CharField(_("Payment Type"), max_length=20)
    status = models.CharField(
        _("Status"), max_length=20, choices=TRANSACTION_STATUSES, default="initiated"
    )
    transaction_type = models.CharField(
        _("Transaction Type"), max_length=20, choices=TRANSACTION_TYPES
    )
    description = models.TextField(_("Description"), blank=True)
    metadata = models.JSONField(_("Metadata"), default=dict)
    failure_message = models.TextField(_("Failure Message"), blank=True, null=True)
    failure_code = models.CharField(
        _("Failure Code"), max_length=50, blank=True, null=True
    )
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    user_agent = models.TextField(_("User Agent"), blank=True, null=True)
    device_fingerprint = models.CharField(
        _("Device Fingerprint"), max_length=255, blank=True, null=True
    )

    # Generic relation to the object being paid for
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "transaction_type"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["moyasar_id"]),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.amount} SAR - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Calculate halalas if not provided (1 SAR = 100 Halalas)
        if not self.amount_halalas and self.amount:
            self.amount_halalas = int(self.amount * 100)
        super().save(*args, **kwargs)


class Refund(models.Model):
    """Refund record for a transaction"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="refunds",
        verbose_name=_("Transaction"),
    )
    moyasar_id = models.CharField(
        _("Moyasar ID"), max_length=255, null=True, blank=True
    )
    amount = models.DecimalField(_("Amount (SAR)"), max_digits=10, decimal_places=2)
    amount_halalas = models.IntegerField(_("Amount (Halalas)"))
    reason = models.TextField(_("Reason"))
    status = models.CharField(
        _("Status"), max_length=20, choices=REFUND_STATUSES, default="initiated"
    )
    refunded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="initiated_refunds",
        verbose_name=_("Refunded By"),
        null=True,
    )
    failure_message = models.TextField(_("Failure Message"), blank=True, null=True)
    failure_code = models.CharField(
        _("Failure Code"), max_length=50, blank=True, null=True
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Refund")
        verbose_name_plural = _("Refunds")
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["status"]),
            models.Index(fields=["moyasar_id"]),
        ]

    def __str__(self):
        return f"{self.transaction} - {self.amount} SAR - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Calculate halalas if not provided (1 SAR = 100 Halalas)
        if not self.amount_halalas and self.amount:
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
