# apps/companiesapp/models.py
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.geoapp.models import Location


# Include validators directly in the file
def phone_number_validator(value):
    """Validate phone number format for Saudi Arabia"""
    # Support for Saudi format (05xxxxxxxx or +9665xxxxxxxx)
    saudi_regex = r"^(05|\+9665)\d{8}$"

    # Support for international format
    intl_regex = r"^\+\d{7,15}$"

    if not (re.match(saudi_regex, value) or re.match(intl_regex, value)):
        raise ValidationError(
            _("Enter a valid phone number (e.g., +966501234567 or 0501234567)")
        )
    return value


def registration_number_validator(value):
    """Validate business registration number in Saudi Arabia"""
    # Most Saudi commercial registration numbers are 10 digits
    if not re.match(r"^\d{10}$", value):
        raise ValidationError(_("Enter a valid 10-digit registration number"))
    return value


class Company(models.Model):
    """Company entity that can have multiple shops/branches"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=255)
    logo = models.ImageField(
        _("Logo"), upload_to="companies/logos/", null=True, blank=True
    )
    registration_number = models.CharField(
        _("Registration Number"),
        max_length=50,
        null=True,
        blank=True,
        validators=[registration_number_validator],
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_companies",
        verbose_name=_("Owner"),
    )
    contact_email = models.EmailField(_("Contact Email"), null=True, blank=True)
    contact_phone = models.CharField(
        _("Contact Phone"), max_length=20, validators=[phone_number_validator]
    )
    description = models.TextField(_("Description"), blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="companies",
        verbose_name=_("Location"),
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    # Subscription status - cached here for quick access
    subscription_status = models.CharField(
        _("Subscription Status"), max_length=20, default="inactive"
    )
    subscription_end_date = models.DateTimeField(
        _("Subscription End Date"), null=True, blank=True
    )

    # Meta data for analytics and sorting
    employee_count = models.PositiveIntegerField(_("Employee Count"), default=0)
    shop_count = models.PositiveIntegerField(_("Shop Count"), default=0)

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["registration_number"]),
            models.Index(fields=["subscription_status"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("company-detail", args=[str(self.id)])

    def update_counts(self):
        """Update shop and employee counts"""
        from apps.employeeapp.models import Employee
        from apps.shopapp.models import Shop

        self.shop_count = Shop.objects.filter(company=self).count()

        # Count all employees across all shops
        shop_ids = Shop.objects.filter(company=self).values_list("id", flat=True)
        self.employee_count = Employee.objects.filter(shop_id__in=shop_ids).count()
        self.save(update_fields=["shop_count", "employee_count"])


class CompanyDocument(models.Model):
    """Documents associated with a company (registration papers, licenses, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Company"),
    )
    title = models.CharField(_("Title"), max_length=255)
    document = models.FileField(_("Document"), upload_to="companies/documents/")
    document_type = models.CharField(_("Document Type"), max_length=50)
    is_verified = models.BooleanField(_("Verified"), default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="verified_company_documents",
        verbose_name=_("Verified By"),
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(_("Verified At"), null=True, blank=True)
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Company Document")
        verbose_name_plural = _("Company Documents")

    def __str__(self):
        return f"{self.company.name} - {self.title}"


class CompanySettings(models.Model):
    """Configuration settings for a company"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name=_("Company"),
    )
    default_language = models.CharField(
        _("Default Language"),
        max_length=10,
        choices=[("en", "English"), ("ar", "Arabic")],
        default="ar",
    )
    notification_email = models.BooleanField(_("Email Notifications"), default=True)
    notification_sms = models.BooleanField(_("SMS Notifications"), default=True)
    auto_approve_bookings = models.BooleanField(
        _("Auto Approve Bookings"), default=True
    )
    require_manager_approval_for_discounts = models.BooleanField(
        _("Require Manager Approval for Discounts"), default=True
    )
    allow_employee_chat = models.BooleanField(_("Allow Employee Chat"), default=True)

    class Meta:
        verbose_name = _("Company Settings")
        verbose_name_plural = _("Company Settings")

    def __str__(self):
        return f"{self.company.name} - Settings"
