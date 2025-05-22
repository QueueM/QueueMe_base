import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class Report(models.Model):
    """Report template definition that can be scheduled or executed on demand"""

    REPORT_TYPE_CHOICES = (
        ("shop_performance", _("Shop Performance")),
        ("specialist_performance", _("Specialist Performance")),
        ("bookings_summary", _("Bookings Summary")),
        ("revenue_summary", _("Revenue Summary")),
        ("customer_insights", _("Customer Insights")),
        ("service_popularity", _("Service Popularity")),
        ("custom", _("Custom")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Report Name"), max_length=255)
    report_type = models.CharField(
        _("Report Type"), max_length=30, choices=REPORT_TYPE_CHOICES
    )
    description = models.TextField(_("Description"), blank=True)

    # Report structure and definition
    template = models.JSONField(_("Template Definition"), default=dict)
    query_definition = models.JSONField(_("Query Definition"), default=dict)

    # Optional shop scope - null means platform-wide report
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="report_templates",
        verbose_name=_("Shop"),
        null=True,
        blank=True,
    )

    # Ownership and timestamps
    is_system = models.BooleanField(
        _("System Report"),
        default=False,
        help_text=_("Whether this is a system-provided report template"),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_report_templates",
        verbose_name=_("Created By"),
        null=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        indexes = [
            models.Index(fields=["report_type"]),
            models.Index(fields=["shop", "is_system"]),
        ]

    def __str__(self):
        shop_name = f" - {self.shop.name}" if self.shop else " - Platform-wide"
        return f"{self.name}{shop_name}"

    def execute(self, parameters=None):
        """
        Execute this report with the given parameters

        Args:
            parameters (dict): Optional parameters to override template defaults

        Returns:
            ReportExecution: The created execution record
        """
        from apps.reportanalyticsapp.services.report_service import ReportService

        # Create a new report execution
        execution = ReportExecution.objects.create(
            name=self.name,
            report_type=self.report_type,
            parameters=parameters or {},
            status="pending",
            created_by=(
                parameters.get("user") if parameters and "user" in parameters else None
            ),
        )

        # Queue report generation (this would typically be handled by a task queue)
        try:
            result = ReportService.generate_report(
                report_id=str(self.id),
                execution_id=str(execution.id),
                parameters=parameters or {},
            )

            # Update execution with results if synchronous
            if result:
                execution.status = "completed"
                execution.result_data = result
                execution.end_time = timezone.now()
                execution.save()

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.end_time = timezone.now()
            execution.save()

        return execution


class AnalyticsSnapshot(models.Model):
    """Base model for storing analytics snapshots"""

    FREQUENCY_CHOICES = (
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly")),
        ("quarterly", _("Quarterly")),
        ("yearly", _("Yearly")),
    )

    SNAPSHOT_TYPE_CHOICES = (
        ("shop", _("Shop")),
        ("specialist", _("Specialist")),
        ("platform", _("Platform")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot_type = models.CharField(
        _("Snapshot Type"), max_length=20, choices=SNAPSHOT_TYPE_CHOICES
    )
    frequency = models.CharField(
        _("Frequency"), max_length=20, choices=FREQUENCY_CHOICES
    )
    snapshot_date = models.DateField(_("Snapshot Date"))
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    data = models.JSONField(_("Data"))
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Analytics Snapshot")
        verbose_name_plural = _("Analytics Snapshots")
        unique_together = ("snapshot_type", "frequency", "snapshot_date")
        indexes = [
            models.Index(fields=["snapshot_type", "frequency", "snapshot_date"]),
        ]

    def __str__(self):
        return f"{self.get_snapshot_type_display()} - {self.get_frequency_display()} - {self.snapshot_date}"


class ShopAnalytics(models.Model):
    """Analytics for a specific shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="analytics", verbose_name=_("Shop")
    )
    date = models.DateField(_("Date"))
    total_bookings = models.IntegerField(_("Total Bookings"), default=0)
    bookings_completed = models.IntegerField(_("Bookings Completed"), default=0)
    bookings_cancelled = models.IntegerField(_("Bookings Cancelled"), default=0)
    bookings_no_show = models.IntegerField(_("Bookings No Show"), default=0)
    total_revenue = models.DecimalField(
        _("Total Revenue"), max_digits=12, decimal_places=2, default=0
    )
    avg_wait_time = models.IntegerField(_("Average Wait Time (minutes)"), default=0)
    peak_hours = models.JSONField(_("Peak Hours"), default=dict)
    customer_ratings = models.DecimalField(
        _("Customer Ratings"), max_digits=3, decimal_places=2, default=0
    )
    new_customers = models.IntegerField(_("New Customers"), default=0)
    returning_customers = models.IntegerField(_("Returning Customers"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Shop Analytics")
        verbose_name_plural = _("Shop Analytics")
        unique_together = ("shop", "date")
        indexes = [
            models.Index(fields=["shop", "date"]),
        ]

    def __str__(self):
        return f"{self.shop.name} - {self.date}"


class SpecialistAnalytics(models.Model):
    """Analytics for a specific specialist"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="analytics",
        verbose_name=_("Specialist"),
    )
    date = models.DateField(_("Date"))
    total_bookings = models.IntegerField(_("Total Bookings"), default=0)
    bookings_completed = models.IntegerField(_("Bookings Completed"), default=0)
    bookings_cancelled = models.IntegerField(_("Bookings Cancelled"), default=0)
    bookings_no_show = models.IntegerField(_("Bookings No Show"), default=0)
    total_service_time = models.IntegerField(
        _("Total Service Time (minutes)"), default=0
    )
    avg_service_duration = models.IntegerField(
        _("Average Service Duration (minutes)"), default=0
    )
    customer_ratings = models.DecimalField(
        _("Customer Ratings"), max_digits=3, decimal_places=2, default=0
    )
    utilization_rate = models.DecimalField(
        _("Utilization Rate"), max_digits=5, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Specialist Analytics")
        verbose_name_plural = _("Specialist Analytics")
        unique_together = ("specialist", "date")
        indexes = [
            models.Index(fields=["specialist", "date"]),
        ]

    def __str__(self):
        specialist_name = f"{self.specialist.employee.first_name} {self.specialist.employee.last_name}"
        return f"{specialist_name} - {self.date}"


class ScheduledReport(models.Model):
    """Scheduled report configuration"""

    FREQUENCY_CHOICES = (
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly")),
        ("quarterly", _("Quarterly")),
    )

    REPORT_TYPE_CHOICES = (
        ("shop_performance", _("Shop Performance")),
        ("specialist_performance", _("Specialist Performance")),
        ("bookings_summary", _("Bookings Summary")),
        ("revenue_summary", _("Revenue Summary")),
        ("custom", _("Custom")),
    )

    RECIPIENT_TYPE_CHOICES = (
        ("user", _("User")),
        ("shop", _("Shop")),
        ("email", _("Email")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Report Name"), max_length=255)
    report_type = models.CharField(
        _("Report Type"), max_length=30, choices=REPORT_TYPE_CHOICES
    )
    frequency = models.CharField(
        _("Frequency"), max_length=20, choices=FREQUENCY_CHOICES
    )

    # Link to report template if using one
    report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        related_name="schedules",
        verbose_name=_("Report Template"),
        null=True,
        blank=True,
    )

    # Filter parameters stored as JSON
    parameters = models.JSONField(_("Parameters"), default=dict)

    # Recipients
    recipient_type = models.CharField(
        _("Recipient Type"), max_length=10, choices=RECIPIENT_TYPE_CHOICES
    )
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_scheduled_reports",
        verbose_name=_("Recipient User"),
        null=True,
        blank=True,
    )
    recipient_shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="received_scheduled_reports",
        verbose_name=_("Recipient Shop"),
        null=True,
        blank=True,
    )
    recipient_email = models.EmailField(_("Recipient Email"), null=True, blank=True)

    # Scheduling
    next_run = models.DateTimeField(_("Next Run"))
    last_run = models.DateTimeField(_("Last Run"), null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_scheduled_reports",
        verbose_name=_("Created By"),
        null=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Scheduled Report")
        verbose_name_plural = _("Scheduled Reports")
        indexes = [
            models.Index(fields=["next_run", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"

    def get_next_run_date(self):
        """Calculate the next run date based on frequency and last run"""
        now = timezone.now()

        if not self.last_run:
            return now

        if self.frequency == "daily":
            return self.last_run + timezone.timedelta(days=1)
        elif self.frequency == "weekly":
            return self.last_run + timezone.timedelta(days=7)
        elif self.frequency == "monthly":
            # Simple approximation - for a more accurate implementation,
            # we'd need to handle month boundaries correctly
            return self.last_run + timezone.timedelta(days=30)
        elif self.frequency == "quarterly":
            return self.last_run + timezone.timedelta(days=90)
        else:
            return now


class ReportExecution(models.Model):
    """Report execution record"""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("running", _("Running")),
        ("completed", _("Completed")),
        ("failed", _("Failed")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_report = models.ForeignKey(
        ScheduledReport,
        on_delete=models.CASCADE,
        related_name="executions",
        verbose_name=_("Scheduled Report"),
        null=True,
        blank=True,
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        related_name="executions",
        verbose_name=_("Report Template"),
        null=True,
        blank=True,
    )
    name = models.CharField(_("Report Name"), max_length=255)
    report_type = models.CharField(_("Report Type"), max_length=30)
    parameters = models.JSONField(_("Parameters"), default=dict)
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    result_data = models.JSONField(_("Result Data"), null=True, blank=True)
    file_url = models.URLField(_("File URL"), null=True, blank=True)
    error_message = models.TextField(_("Error Message"), blank=True)
    start_time = models.DateTimeField(_("Start Time"), auto_now_add=True)
    end_time = models.DateTimeField(_("End Time"), null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="report_executions",
        verbose_name=_("Created By"),
        null=True,
    )

    class Meta:
        verbose_name = _("Report Execution")
        verbose_name_plural = _("Report Executions")
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["status", "start_time"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def execution_time(self):
        """Calculate execution time in seconds"""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class AnomalyDetection(models.Model):
    """Anomaly detection record"""

    SEVERITY_CHOICES = (
        ("low", _("Low")),
        ("medium", _("Medium")),
        ("high", _("High")),
    )

    ENTITY_TYPE_CHOICES = (
        ("shop", _("Shop")),
        ("specialist", _("Specialist")),
        ("service", _("Service")),
        ("platform", _("Platform")),
    )

    METRIC_TYPE_CHOICES = (
        ("booking_volume", _("Booking Volume")),
        ("revenue", _("Revenue")),
        ("cancellation_rate", _("Cancellation Rate")),
        ("no_show_rate", _("No Show Rate")),
        ("rating", _("Rating")),
        ("wait_time", _("Wait Time")),
        ("utilization", _("Utilization")),
        ("other", _("Other")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(
        _("Entity Type"), max_length=20, choices=ENTITY_TYPE_CHOICES
    )
    entity_id = models.UUIDField(_("Entity ID"))
    metric_type = models.CharField(
        _("Metric Type"), max_length=20, choices=METRIC_TYPE_CHOICES
    )
    detection_date = models.DateField(_("Detection Date"))
    expected_value = models.DecimalField(
        _("Expected Value"), max_digits=12, decimal_places=2
    )
    actual_value = models.DecimalField(
        _("Actual Value"), max_digits=12, decimal_places=2
    )
    deviation_percentage = models.DecimalField(
        _("Deviation Percentage"), max_digits=10, decimal_places=2
    )
    severity = models.CharField(_("Severity"), max_length=10, choices=SEVERITY_CHOICES)
    description = models.TextField(_("Description"))
    is_acknowledged = models.BooleanField(_("Acknowledged"), default=False)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="acknowledged_anomalies",
        verbose_name=_("Acknowledged By"),
        null=True,
        blank=True,
    )
    acknowledged_at = models.DateTimeField(_("Acknowledged At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Anomaly Detection")
        verbose_name_plural = _("Anomaly Detections")
        ordering = ["-detection_date", "-severity"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["detection_date"]),
            models.Index(fields=["is_acknowledged"]),
        ]

    def __str__(self):
        return f"{self.get_entity_type_display()} - {self.get_metric_type_display()} - {self.detection_date}"

    def acknowledge(self, user):
        """Mark anomaly as acknowledged"""
        self.is_acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
