import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.shopapp.models import Shop
from apps.shopDashboardApp.constants import (
    CHART_TYPE_CHOICES,
    DATA_GRANULARITY_CHOICES,
    DATA_GRANULARITY_DAILY,
    KPI_CATEGORY_CHOICES,
    REPORT_FREQUENCY_CHOICES,
    TIME_PERIOD_CHOICES,
    TIME_PERIOD_MONTH,
    WIDGET_TYPE_CHOICES,
)


class DashboardSettings(models.Model):
    """Dashboard settings for a shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="dashboard_settings",
        verbose_name=_("Shop"),
    )
    default_date_range = models.CharField(
        _("Default Date Range"),
        max_length=20,
        choices=TIME_PERIOD_CHOICES,
        default=TIME_PERIOD_MONTH,
    )
    auto_refresh_interval = models.PositiveIntegerField(
        _("Auto Refresh Interval (seconds)"), default=0  # 0 means no auto-refresh
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    custom_theme = models.JSONField(_("Custom Theme"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Dashboard Settings")
        verbose_name_plural = _("Dashboard Settings")

    def __str__(self):
        return f"{self.shop.name} - Dashboard Settings"


class DashboardLayout(models.Model):
    """Saved dashboard layout configuration"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="dashboard_layouts",
        verbose_name=_("Shop"),
    )
    name = models.CharField(_("Layout Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    is_default = models.BooleanField(_("Default Layout"), default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_dashboard_layouts",
        verbose_name=_("Created By"),
        null=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Dashboard Layout")
        verbose_name_plural = _("Dashboard Layouts")
        unique_together = ("shop", "name")

    def __str__(self):
        return f"{self.shop.name} - {self.name}"

    def save(self, *args, **kwargs):
        """Ensure only one default layout per shop"""
        if self.is_default:
            # Set all other layouts for this shop to non-default
            DashboardLayout.objects.filter(shop=self.shop, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class DashboardWidget(models.Model):
    """Widget displayed on the dashboard"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layout = models.ForeignKey(
        DashboardLayout,
        on_delete=models.CASCADE,
        related_name="widgets",
        verbose_name=_("Dashboard Layout"),
    )
    title = models.CharField(_("Widget Title"), max_length=100)
    widget_type = models.CharField(_("Widget Type"), max_length=20, choices=WIDGET_TYPE_CHOICES)
    category = models.CharField(
        _("Category"),
        max_length=20,
        choices=KPI_CATEGORY_CHOICES,
        blank=True,
        null=True,
    )
    kpi_key = models.CharField(_("KPI Key"), max_length=50, blank=True, null=True)
    chart_type = models.CharField(
        _("Chart Type"),
        max_length=20,
        choices=CHART_TYPE_CHOICES,
        blank=True,
        null=True,
    )
    data_source = models.CharField(_("Data Source"), max_length=50, blank=True, null=True)
    data_granularity = models.CharField(
        _("Data Granularity"),
        max_length=20,
        choices=DATA_GRANULARITY_CHOICES,
        default=DATA_GRANULARITY_DAILY,
    )
    config = models.JSONField(_("Widget Configuration"), default=dict, blank=True)
    position = models.JSONField(
        _("Position"),
        default=dict,
        help_text=_("JSON with grid position (x, y, width, height)"),
    )
    is_visible = models.BooleanField(_("Visible"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Dashboard Widget")
        verbose_name_plural = _("Dashboard Widgets")
        ordering = ["layout", "position"]

    def __str__(self):
        return f"{self.layout.name} - {self.title}"


class ScheduledReport(models.Model):
    """Scheduled dashboard report configuration"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="scheduled_reports",
        verbose_name=_("Shop"),
    )
    name = models.CharField(_("Report Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    frequency = models.CharField(_("Frequency"), max_length=20, choices=REPORT_FREQUENCY_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(
        _("Day of Week"),
        null=True,
        blank=True,
        help_text=_("0=Sunday, 6=Saturday. For weekly reports."),
    )
    day_of_month = models.PositiveSmallIntegerField(
        _("Day of Month"),
        null=True,
        blank=True,
        help_text=_("1-31. For monthly reports."),
    )
    time_of_day = models.TimeField(_("Time of Day"))
    recipients = models.JSONField(_("Recipients"), default=list)
    kpis_included = models.JSONField(_("KPIs Included"), default=list)
    charts_included = models.JSONField(_("Charts Included"), default=list)
    date_range = models.CharField(_("Date Range"), max_length=20, choices=TIME_PERIOD_CHOICES)
    is_active = models.BooleanField(_("Active"), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_reports",
        verbose_name=_("Created By"),
        null=True,
    )
    last_sent_at = models.DateTimeField(_("Last Sent At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Scheduled Report")
        verbose_name_plural = _("Scheduled Reports")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shop.name} - {self.name}"


class SavedFilter(models.Model):
    """Saved filter for dashboard data"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="dashboard_filters",
        verbose_name=_("Shop"),
    )
    name = models.CharField(_("Filter Name"), max_length=100)
    filter_config = models.JSONField(_("Filter Configuration"))
    is_favorite = models.BooleanField(_("Favorite"), default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="dashboard_filters",
        verbose_name=_("Created By"),
        null=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Saved Filter")
        verbose_name_plural = _("Saved Filters")
        unique_together = ("shop", "name")

    def __str__(self):
        return f"{self.shop.name} - {self.name}"


class DashboardPreference(models.Model):
    """User-specific dashboard preferences"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="dashboard_preference",
        verbose_name=_("User"),
    )
    preferred_layout = models.ForeignKey(
        DashboardLayout,
        on_delete=models.SET_NULL,
        related_name="preferred_by_users",
        verbose_name=_("Preferred Layout"),
        null=True,
        blank=True,
    )
    favorite_kpis = models.JSONField(_("Favorite KPIs"), default=list, blank=True)
    preferred_date_range = models.CharField(
        _("Preferred Date Range"),
        max_length=20,
        choices=TIME_PERIOD_CHOICES,
        default=TIME_PERIOD_MONTH,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Dashboard Preference")
        verbose_name_plural = _("Dashboard Preferences")

    def __str__(self):
        return f"{self.user.phone_number} - Dashboard Preferences"
