import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.employeeapp.models import Employee
from apps.shopapp.models import Shop


class Conversation(models.Model):
    """Chat conversation between customer and shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name=_("Customer"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name=_("Shop"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        unique_together = ("customer", "shop")
        indexes = [
            models.Index(fields=["customer", "shop"]),
            models.Index(fields=["updated_at"]),  # For sorting by recent activity
        ]
        ordering = ["-updated_at"]  # Most recent conversations first

    def __str__(self):
        return f"{self.customer.phone_number} - {self.shop.name}"


class Message(models.Model):
    """Chat message within a conversation"""

    TYPE_CHOICES = (
        ("text", _("Text")),
        ("image", _("Image")),
        ("video", _("Video")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Conversation"),
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name=_("Sender"),
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        related_name="messages",
        verbose_name=_("Employee"),
        null=True,
        blank=True,
    )
    content = models.TextField(_("Content"))
    message_type = models.CharField(
        _("Type"), max_length=10, choices=TYPE_CHOICES, default="text"
    )
    media_url = models.URLField(_("Media URL"), null=True, blank=True)
    is_read = models.BooleanField(_("Read"), default=False)
    read_at = models.DateTimeField(_("Read At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ["created_at"]  # Messages ordered chronologically
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["is_read"]),  # For filtering unread messages
        ]

    def __str__(self):
        return (
            f"{self.sender.phone_number} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
        )


class Presence(models.Model):
    """User online/offline status for a conversation"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="presence_records",
        verbose_name=_("User"),
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="presence_records",
        verbose_name=_("Conversation"),
    )
    is_online = models.BooleanField(_("Online"), default=False)
    last_seen = models.DateTimeField(_("Last Seen"), auto_now=True)

    class Meta:
        verbose_name = _("Presence")
        verbose_name_plural = _("Presences")
        unique_together = ("user", "conversation")

    def __str__(self):
        status = "Online" if self.is_online else "Offline"
        return f"{self.user.phone_number} - {status}"


class TypingStatus(models.Model):
    """User typing status in a conversation"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="typing_statuses",
        verbose_name=_("User"),
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="typing_statuses",
        verbose_name=_("Conversation"),
    )
    is_typing = models.BooleanField(_("Typing"), default=False)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Typing Status")
        verbose_name_plural = _("Typing Statuses")
        unique_together = ("user", "conversation")

    def __str__(self):
        return (
            f"{self.user.phone_number} - {'Typing' if self.is_typing else 'Not typing'}"
        )
