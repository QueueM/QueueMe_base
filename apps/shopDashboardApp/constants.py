from django.utils.translation import gettext_lazy as _

# Time period constants
TIME_PERIOD_TODAY = "today"
TIME_PERIOD_YESTERDAY = "yesterday"
TIME_PERIOD_WEEK = "week"
TIME_PERIOD_MONTH = "month"
TIME_PERIOD_QUARTER = "quarter"
TIME_PERIOD_YEAR = "year"
TIME_PERIOD_CUSTOM = "custom"

TIME_PERIOD_CHOICES = (
    (TIME_PERIOD_TODAY, _("Today")),
    (TIME_PERIOD_YESTERDAY, _("Yesterday")),
    (TIME_PERIOD_WEEK, _("This Week")),
    (TIME_PERIOD_MONTH, _("This Month")),
    (TIME_PERIOD_QUARTER, _("This Quarter")),
    (TIME_PERIOD_YEAR, _("This Year")),
    (TIME_PERIOD_CUSTOM, _("Custom Range")),
)

# Dashboard KPI categories
KPI_CATEGORY_REVENUE = "revenue"
KPI_CATEGORY_BOOKINGS = "bookings"
KPI_CATEGORY_CUSTOMERS = "customers"
KPI_CATEGORY_SERVICES = "services"
KPI_CATEGORY_QUEUE = "queue"
KPI_CATEGORY_REVIEWS = "reviews"
KPI_CATEGORY_SPECIALISTS = "specialists"
KPI_CATEGORY_ENGAGEMENT = "engagement"

KPI_CATEGORY_CHOICES = (
    (KPI_CATEGORY_REVENUE, _("Revenue")),
    (KPI_CATEGORY_BOOKINGS, _("Bookings")),
    (KPI_CATEGORY_CUSTOMERS, _("Customers")),
    (KPI_CATEGORY_SERVICES, _("Services")),
    (KPI_CATEGORY_QUEUE, _("Queue")),
    (KPI_CATEGORY_REVIEWS, _("Reviews")),
    (KPI_CATEGORY_SPECIALISTS, _("Specialists")),
    (KPI_CATEGORY_ENGAGEMENT, _("Engagement")),
)

# Chart types
CHART_TYPE_LINE = "line"
CHART_TYPE_BAR = "bar"
CHART_TYPE_PIE = "pie"
CHART_TYPE_DOUGHNUT = "doughnut"
CHART_TYPE_RADAR = "radar"
CHART_TYPE_POLAR = "polar"
CHART_TYPE_TABLE = "table"
CHART_TYPE_HEATMAP = "heatmap"

CHART_TYPE_CHOICES = (
    (CHART_TYPE_LINE, _("Line Chart")),
    (CHART_TYPE_BAR, _("Bar Chart")),
    (CHART_TYPE_PIE, _("Pie Chart")),
    (CHART_TYPE_DOUGHNUT, _("Doughnut Chart")),
    (CHART_TYPE_RADAR, _("Radar Chart")),
    (CHART_TYPE_POLAR, _("Polar Chart")),
    (CHART_TYPE_TABLE, _("Table")),
    (CHART_TYPE_HEATMAP, _("Heatmap")),
)

# Data granularity
DATA_GRANULARITY_HOURLY = "hourly"
DATA_GRANULARITY_DAILY = "daily"
DATA_GRANULARITY_WEEKLY = "weekly"
DATA_GRANULARITY_MONTHLY = "monthly"
DATA_GRANULARITY_QUARTERLY = "quarterly"
DATA_GRANULARITY_YEARLY = "yearly"

DATA_GRANULARITY_CHOICES = (
    (DATA_GRANULARITY_HOURLY, _("Hourly")),
    (DATA_GRANULARITY_DAILY, _("Daily")),
    (DATA_GRANULARITY_WEEKLY, _("Weekly")),
    (DATA_GRANULARITY_MONTHLY, _("Monthly")),
    (DATA_GRANULARITY_QUARTERLY, _("Quarterly")),
    (DATA_GRANULARITY_YEARLY, _("Yearly")),
)

# Report scheduling frequencies
REPORT_FREQUENCY_DAILY = "daily"
REPORT_FREQUENCY_WEEKLY = "weekly"
REPORT_FREQUENCY_MONTHLY = "monthly"
REPORT_FREQUENCY_QUARTERLY = "quarterly"

REPORT_FREQUENCY_CHOICES = (
    (REPORT_FREQUENCY_DAILY, _("Daily")),
    (REPORT_FREQUENCY_WEEKLY, _("Weekly")),
    (REPORT_FREQUENCY_MONTHLY, _("Monthly")),
    (REPORT_FREQUENCY_QUARTERLY, _("Quarterly")),
)

# Widget types
WIDGET_TYPE_KPI = "kpi"
WIDGET_TYPE_CHART = "chart"
WIDGET_TYPE_TABLE = "table"
WIDGET_TYPE_ACTIVITY = "activity"
WIDGET_TYPE_NOTIFICATIONS = "notifications"
WIDGET_TYPE_CALENDAR = "calendar"

WIDGET_TYPE_CHOICES = (
    (WIDGET_TYPE_KPI, _("KPI Card")),
    (WIDGET_TYPE_CHART, _("Chart")),
    (WIDGET_TYPE_TABLE, _("Table")),
    (WIDGET_TYPE_ACTIVITY, _("Activity Feed")),
    (WIDGET_TYPE_NOTIFICATIONS, _("Notifications")),
    (WIDGET_TYPE_CALENDAR, _("Calendar")),
)

# Default KPIs
DEFAULT_KPIS = [
    {
        "key": "total_revenue",
        "name": _("Total Revenue"),
        "category": KPI_CATEGORY_REVENUE,
        "format": "currency",
    },
    {
        "key": "avg_revenue_per_booking",
        "name": _("Average Revenue per Booking"),
        "category": KPI_CATEGORY_REVENUE,
        "format": "currency",
    },
    {
        "key": "total_bookings",
        "name": _("Total Bookings"),
        "category": KPI_CATEGORY_BOOKINGS,
        "format": "number",
    },
    {
        "key": "completed_bookings",
        "name": _("Completed Bookings"),
        "category": KPI_CATEGORY_BOOKINGS,
        "format": "number",
    },
    {
        "key": "cancellation_rate",
        "name": _("Cancellation Rate"),
        "category": KPI_CATEGORY_BOOKINGS,
        "format": "percentage",
    },
    {
        "key": "no_show_rate",
        "name": _("No-Show Rate"),
        "category": KPI_CATEGORY_BOOKINGS,
        "format": "percentage",
    },
    {
        "key": "total_customers",
        "name": _("Total Customers"),
        "category": KPI_CATEGORY_CUSTOMERS,
        "format": "number",
    },
    {
        "key": "new_customers",
        "name": _("New Customers"),
        "category": KPI_CATEGORY_CUSTOMERS,
        "format": "number",
    },
    {
        "key": "returning_customer_rate",
        "name": _("Returning Customer Rate"),
        "category": KPI_CATEGORY_CUSTOMERS,
        "format": "percentage",
    },
    {
        "key": "avg_queue_wait_time",
        "name": _("Average Queue Wait Time"),
        "category": KPI_CATEGORY_QUEUE,
        "format": "time",
    },
    {
        "key": "avg_rating",
        "name": _("Average Rating"),
        "category": KPI_CATEGORY_REVIEWS,
        "format": "rating",
    },
    {
        "key": "most_popular_service",
        "name": _("Most Popular Service"),
        "category": KPI_CATEGORY_SERVICES,
        "format": "text",
    },
    {
        "key": "top_specialist",
        "name": _("Top Specialist"),
        "category": KPI_CATEGORY_SPECIALISTS,
        "format": "text",
    },
    {
        "key": "reel_views",
        "name": _("Reel Views"),
        "category": KPI_CATEGORY_ENGAGEMENT,
        "format": "number",
    },
    {
        "key": "story_views",
        "name": _("Story Views"),
        "category": KPI_CATEGORY_ENGAGEMENT,
        "format": "number",
    },
]
