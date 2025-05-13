import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Customer(models.Model):
    """
    Customer profile model extending User information
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "authapp.User",
        on_delete=models.CASCADE,
        related_name="customer_profile",
        verbose_name=_("User"),
    )
    name = models.CharField(_("Name"), max_length=255, blank=True)
    avatar = models.ImageField(
        _("Avatar"),
        upload_to="customers/avatars/",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"])],
        null=True,
        blank=True,
    )
    city = models.CharField(_("City"), max_length=100, blank=True)
    location = models.ForeignKey(
        "geoapp.Location",
        on_delete=models.SET_NULL,
        related_name="customers",
        verbose_name=_("Location"),
        null=True,
        blank=True,
    )
    birth_date = models.DateField(_("Birth Date"), null=True, blank=True)
    bio = models.TextField(_("Bio"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.name or 'Unnamed'}"


class CustomerPreference(models.Model):
    """
    Customer preferences for app settings and notifications
    """

    LANGUAGE_CHOICES = (
        ("en", _("English")),
        ("ar", _("Arabic")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="preferences",
        verbose_name=_("Customer"),
    )
    language = models.CharField(
        _("Language Preference"), max_length=2, choices=LANGUAGE_CHOICES, default="en"
    )
    notification_enabled = models.BooleanField(_("Notifications Enabled"), default=True)
    email_notifications = models.BooleanField(_("Email Notifications"), default=True)
    sms_notifications = models.BooleanField(_("SMS Notifications"), default=True)
    push_notifications = models.BooleanField(_("Push Notifications"), default=True)
    appointment_reminder_minutes = models.IntegerField(
        _("Appointment Reminder Minutes Before"),
        default=30,
        help_text=_("Minutes before appointment to send reminder"),
    )
    marketing_opt_in = models.BooleanField(_("Marketing Opt-In"), default=False)
    dark_mode = models.BooleanField(_("Dark Mode"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Customer Preference")
        verbose_name_plural = _("Customer Preferences")

    def __str__(self):
        return f"Preferences for {self.customer}"


class SavedPaymentMethod(models.Model):
    """
    Saved payment methods for quick checkout
    """

    PAYMENT_TYPE_CHOICES = (
        ("card", _("Credit/Debit Card")),
        ("stcpay", _("STC Pay")),
        ("mada", _("Mada")),
        ("apple_pay", _("Apple Pay")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="payment_methods",
        verbose_name=_("Customer"),
    )
    payment_type = models.CharField(_("Payment Type"), max_length=20, choices=PAYMENT_TYPE_CHOICES)
    token = models.CharField(_("Payment Token"), max_length=255)
    last_digits = models.CharField(_("Last Digits"), max_length=4, null=True, blank=True)
    expiry_month = models.CharField(_("Expiry Month"), max_length=2, null=True, blank=True)
    expiry_year = models.CharField(_("Expiry Year"), max_length=4, null=True, blank=True)
    card_brand = models.CharField(_("Card Brand"), max_length=50, null=True, blank=True)
    is_default = models.BooleanField(_("Default Payment Method"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Saved Payment Method")
        verbose_name_plural = _("Saved Payment Methods")
        indexes = [
            models.Index(fields=["is_default"]),
            models.Index(fields=["payment_type"]),
        ]

    def __str__(self):
        if self.payment_type == "card" and self.last_digits:
            return f"{self.customer} - {self.get_payment_type_display()} (**** {self.last_digits})"
        return f"{self.customer} - {self.get_payment_type_display()}"

    def save(self, *args, **kwargs):
        # If this is set as default, unset other default payment methods
        if self.is_default:
            SavedPaymentMethod.objects.filter(customer=self.customer, is_default=True).update(
                is_default=False
            )

        # If this is the only payment method, make it default
        if not self.pk and not SavedPaymentMethod.objects.filter(customer=self.customer).exists():
            self.is_default = True

        super().save(*args, **kwargs)


class FavoriteShop(models.Model):
    """
    Customer's favorite shops
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="favorite_shops",
        verbose_name=_("Customer"),
    )
    shop = models.ForeignKey(
        "shopapp.Shop",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("Shop"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Favorite Shop")
        verbose_name_plural = _("Favorite Shops")
        unique_together = ("customer", "shop")

    def __str__(self):
        return f"{self.customer} - {self.shop}"


class FavoriteSpecialist(models.Model):
    """
    Customer's favorite specialists
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="favorite_specialists",
        verbose_name=_("Customer"),
    )
    specialist = models.ForeignKey(
        "specialistsapp.Specialist",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("Specialist"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Favorite Specialist")
        verbose_name_plural = _("Favorite Specialists")
        unique_together = ("customer", "specialist")

    def __str__(self):
        return f"{self.customer} - {self.specialist}"


class FavoriteService(models.Model):
    """
    Customer's favorite services
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="favorite_services",
        verbose_name=_("Customer"),
    )
    service = models.ForeignKey(
        "serviceapp.Service",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("Service"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Favorite Service")
        verbose_name_plural = _("Favorite Services")
        unique_together = ("customer", "service")

    def __str__(self):
        return f"{self.customer} - {self.service}"


class CustomerCategory(models.Model):
    """
    Categories that customer has shown interest in, used for personalization
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="category_interests",
        verbose_name=_("Customer"),
    )
    category = models.ForeignKey(
        "categoriesapp.Category",
        on_delete=models.CASCADE,
        related_name="interested_customers",
        verbose_name=_("Category"),
    )
    affinity_score = models.FloatField(
        _("Affinity Score"),
        default=0.0,
        help_text=_("Score indicating customer interest level (0-1)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Customer Category Interest")
        verbose_name_plural = _("Customer Category Interests")
        unique_together = ("customer", "category")
        ordering = ["-affinity_score"]

    def __str__(self):
        return f"{self.customer} - {self.category} ({self.affinity_score:.2f})"
