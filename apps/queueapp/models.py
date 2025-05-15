import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class Queue(models.Model):
    """Queue for a shop"""

    STATUS_CHOICES = (
        ("open", _("Open")),
        ("closed", _("Closed")),
        ("paused", _("Paused")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="queues", verbose_name=_("Shop")
    )
    name = models.CharField(_("Name"), max_length=100)
    status = models.CharField(_("Status"), max_length=10, choices=STATUS_CHOICES, default="open")
    max_capacity = models.PositiveIntegerField(
        _("Maximum Capacity"), default=0
    )  # 0 means unlimited
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Queue")
        verbose_name_plural = _("Queues")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["shop", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.shop.name} - {self.name}"

    def is_at_capacity(self):
        """Check if queue is at maximum capacity"""
        if self.max_capacity == 0:  # Unlimited
            return False

        active_count = self.tickets.filter(status__in=["waiting", "called"]).count()
        return active_count >= self.max_capacity


class QueueTicket(models.Model):
    """Queue ticket for a customer"""

    STATUS_CHOICES = (
        ("waiting", _("Waiting")),
        ("called", _("Called")),
        ("serving", _("Serving")),
        ("served", _("Served")),
        ("skipped", _("Skipped")),
        ("cancelled", _("Cancelled")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue = models.ForeignKey(
        Queue, on_delete=models.CASCADE, related_name="tickets", verbose_name=_("Queue")
    )
    ticket_number = models.CharField(_("Ticket Number"), max_length=20)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="queue_tickets",
        verbose_name=_("Customer"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="queue_tickets",
        verbose_name=_("Service"),
        null=True,
        blank=True,
    )
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.SET_NULL,
        related_name="queue_tickets",
        verbose_name=_("Specialist"),
        null=True,
        blank=True,
    )
    status = models.CharField(_("Status"), max_length=10, choices=STATUS_CHOICES, default="waiting")
    position = models.PositiveIntegerField(_("Position"))
    estimated_wait_time = models.PositiveIntegerField(_("Estimated Wait Time (minutes)"), default=0)
    actual_wait_time = models.PositiveIntegerField(
        _("Actual Wait Time (minutes)"), null=True, blank=True
    )
    notes = models.TextField(_("Notes"), blank=True)
    join_time = models.DateTimeField(_("Join Time"), auto_now_add=True)
    called_time = models.DateTimeField(_("Called Time"), null=True, blank=True)
    serve_time = models.DateTimeField(_("Serve Time"), null=True, blank=True)
    complete_time = models.DateTimeField(_("Complete Time"), null=True, blank=True)

    class Meta:
        verbose_name = _("Queue Ticket")
        verbose_name_plural = _("Queue Tickets")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["position"]),
            models.Index(fields=["queue", "status"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["join_time"]),
            models.Index(fields=["specialist", "status"]),
        ]

    def __str__(self):
        return f"{self.queue.shop.name} - {self.ticket_number} - {self.customer.phone_number}"
