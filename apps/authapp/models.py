import random
import string
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

from apps.authapp.constants import OTP_LENGTH
from apps.authapp.managers import UserManager
from apps.authapp.validators import normalize_phone_number, validate_phone_number


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses phone number for authentication instead of usernames.
    """

    USER_TYPE_CHOICES = (
        ("customer", _("Customer")),
        ("employee", _("Employee")),
        ("admin", _("Admin")),
    )

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("ID")
    )
    phone_number = models.CharField(
        _("Phone Number"),
        max_length=20,
        unique=True,
        validators=[validate_phone_number],
    )
    email = models.EmailField(_("Email Address"), blank=True, null=True)
    first_name = models.CharField(_("First Name"), max_length=150, blank=True)
    last_name = models.CharField(_("Last Name"), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _("Staff Status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_verified = models.BooleanField(
        _("Verified"),
        default=False,
        help_text=_("Designates whether this user has verified their phone number."),
    )
    user_type = models.CharField(
        _("User Type"),
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default="customer",
    )
    language_preference = models.CharField(
        _("Language Preference"),
        max_length=10,
        choices=[("en", _("English")), ("ar", _("Arabic"))],
        default="en",
    )
    date_joined = models.DateTimeField(_("Date Joined"), default=timezone.now)
    last_login = models.DateTimeField(_("Last Login"), null=True, blank=True)

    # Field tracker for detecting changes
    tracker = FieldTracker(fields=["is_active", "is_verified", "user_type"])

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["user_type"]),
        ]

    def __str__(self):
        return self.phone_number

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    @property
    def profile_completed(self):
        """Check if user has completed their profile with essential information."""
        # Define what makes a completed profile based on user_type
        if not (self.first_name and self.last_name):
            return False

        if self.user_type == "customer":
            # For customers, basic personal info is sufficient
            return bool(self.phone_number and self.is_verified)
        elif self.user_type == "employee":
            # For employees, we might want to check if they have an employee profile
            try:
                return bool(
                    hasattr(self, "employee") and getattr(self, "employee", None)
                )
            except BaseException:
                return False
        else:
            # For admins or other types
            return bool(self.email)

    def save(self, *args, **kwargs):
        # Normalize phone number before saving
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)


class OTP(models.Model):
    """
    One-Time Password model for phone verification.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("ID")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otps",
        null=True,
        blank=True,
        verbose_name=_("User"),
    )
    phone_number = models.CharField(
        _("Phone Number"), max_length=20, validators=[validate_phone_number]
    )
    code = models.CharField(_("OTP Code"), max_length=10)
    is_used = models.BooleanField(_("Is Used"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    expires_at = models.DateTimeField(_("Expires At"))
    verification_attempts = models.PositiveSmallIntegerField(
        _("Verification Attempts"),
        default=0,
        help_text=_("Number of times a verification has been attempted with this OTP."),
    )

    class Meta:
        verbose_name = _("OTP")
        verbose_name_plural = _("OTPs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.phone_number} - {self.code}"

    @staticmethod
    def generate_otp(length=OTP_LENGTH):
        """Generate a numeric OTP code with the specified length."""
        return "".join(random.choices(string.digits, k=length))

    def is_valid(self):
        """Check if OTP is valid (not used, not expired, and has attempts left)."""
        from apps.authapp.constants import MAX_OTP_VERIFICATION_ATTEMPTS

        return (
            not self.is_used
            and timezone.now() < self.expires_at
            and self.verification_attempts < MAX_OTP_VERIFICATION_ATTEMPTS
        )

    def save(self, *args, **kwargs):
        # Normalize phone number before saving
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)


class SecurityEvent(models.Model):
    """
    Model for storing security-related events for auditing purposes.
    """

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    event_type = models.CharField(max_length=100)
    details = models.JSONField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="info")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "event_type", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
        ]

    def __str__(self):
        # Use the related object correctly
        user_identifier = "Unknown"
        if self.user is not None:
            user_identifier = getattr(self.user, "phone_number", "Unknown")
        return f"{self.event_type} - {user_identifier} - {self.created_at}"


class AuthToken(models.Model):
    """
    Authentication tokens for API access
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    token = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(max_length=100, null=True, blank=True)
    device_info = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Authentication Token")
        verbose_name_plural = _("Authentication Tokens")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        # Use the related object correctly
        user_info = "Unknown"
        if self.user is not None:
            user_info = getattr(self.user, "phone_number", "Unknown")
        return f"Token for {user_info} ({self.created_at})"

    @property
    def is_expired(self):
        """Check if token is expired"""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at


class PasswordResetToken(models.Model):
    """
    Password reset tokens with expiration
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = _("Password Reset Token")
        verbose_name_plural = _("Password Reset Tokens")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        # Use the related object correctly
        user_info = "Unknown"
        if self.user is not None:
            user_info = getattr(self.user, "phone_number", "Unknown")
        return f"Reset token for {user_info} ({self.created_at})"

    @property
    def is_expired(self):
        """Check if token is expired"""
        return timezone.now() >= self.expires_at


class LoginAttempt(models.Model):
    """
    Track login attempts for security monitoring and account lockout
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_attempts",
        null=True,
        blank=True,
    )
    success = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    username_attempted = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The username/email/phone that was attempted"),
    )
    failure_reason = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = _("Login Attempt")
        verbose_name_plural = _("Login Attempts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["success"]),
            models.Index(fields=["username_attempted"]),
        ]

    def __str__(self):
        # Use the related object correctly
        if self.user is not None:
            user_str = getattr(self.user, "phone_number", "Unknown")
        else:
            user_str = self.username_attempted or "Unknown"
        status = "Successful" if self.success else "Failed"
        return f"{status} login attempt for {user_str} ({self.created_at})"
