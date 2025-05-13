from django.utils.translation import gettext_lazy as _

# Verification status choices
VERIFICATION_STATUS_PENDING = "pending"
VERIFICATION_STATUS_APPROVED = "approved"
VERIFICATION_STATUS_REJECTED = "rejected"
VERIFICATION_STATUS_CHOICES = [
    (VERIFICATION_STATUS_PENDING, _("Pending")),
    (VERIFICATION_STATUS_APPROVED, _("Approved")),
    (VERIFICATION_STATUS_REJECTED, _("Rejected")),
]

# System Setting Categories
SETTING_CATEGORY_GENERAL = "general"
SETTING_CATEGORY_SECURITY = "security"
SETTING_CATEGORY_BOOKING = "booking"
SETTING_CATEGORY_NOTIFICATIONS = "notifications"
SETTING_CATEGORY_PAYMENT = "payment"
SETTING_CATEGORY_APPEARANCE = "appearance"
SETTING_CATEGORY_CHOICES = [
    (SETTING_CATEGORY_GENERAL, _("General")),
    (SETTING_CATEGORY_SECURITY, _("Security")),
    (SETTING_CATEGORY_BOOKING, _("Booking")),
    (SETTING_CATEGORY_NOTIFICATIONS, _("Notifications")),
    (SETTING_CATEGORY_PAYMENT, _("Payment")),
    (SETTING_CATEGORY_APPEARANCE, _("Appearance")),
]

# Notification levels
NOTIFICATION_LEVEL_INFO = "info"
NOTIFICATION_LEVEL_WARNING = "warning"
NOTIFICATION_LEVEL_ERROR = "error"
NOTIFICATION_LEVEL_CRITICAL = "critical"
NOTIFICATION_LEVEL_CHOICES = [
    (NOTIFICATION_LEVEL_INFO, _("Information")),
    (NOTIFICATION_LEVEL_WARNING, _("Warning")),
    (NOTIFICATION_LEVEL_ERROR, _("Error")),
    (NOTIFICATION_LEVEL_CRITICAL, _("Critical")),
]

# Support ticket status choices
TICKET_STATUS_OPEN = "open"
TICKET_STATUS_IN_PROGRESS = "in_progress"
TICKET_STATUS_WAITING = "waiting_for_customer"
TICKET_STATUS_RESOLVED = "resolved"
TICKET_STATUS_CLOSED = "closed"
TICKET_STATUS_CHOICES = [
    (TICKET_STATUS_OPEN, _("Open")),
    (TICKET_STATUS_IN_PROGRESS, _("In Progress")),
    (TICKET_STATUS_WAITING, _("Waiting for Customer")),
    (TICKET_STATUS_RESOLVED, _("Resolved")),
    (TICKET_STATUS_CLOSED, _("Closed")),
]

# Support ticket priority choices
TICKET_PRIORITY_LOW = "low"
TICKET_PRIORITY_MEDIUM = "medium"
TICKET_PRIORITY_HIGH = "high"
TICKET_PRIORITY_URGENT = "urgent"
TICKET_PRIORITY_CHOICES = [
    (TICKET_PRIORITY_LOW, _("Low")),
    (TICKET_PRIORITY_MEDIUM, _("Medium")),
    (TICKET_PRIORITY_HIGH, _("High")),
    (TICKET_PRIORITY_URGENT, _("Urgent")),
]

# Support ticket category choices
TICKET_CATEGORY_ACCOUNT = "account"
TICKET_CATEGORY_BOOKING = "booking"
TICKET_CATEGORY_PAYMENT = "payment"
TICKET_CATEGORY_TECHNICAL = "technical"
TICKET_CATEGORY_FEATURE = "feature_request"
TICKET_CATEGORY_OTHER = "other"
TICKET_CATEGORY_CHOICES = [
    (TICKET_CATEGORY_ACCOUNT, _("Account")),
    (TICKET_CATEGORY_BOOKING, _("Booking")),
    (TICKET_CATEGORY_PAYMENT, _("Payment")),
    (TICKET_CATEGORY_TECHNICAL, _("Technical")),
    (TICKET_CATEGORY_FEATURE, _("Feature Request")),
    (TICKET_CATEGORY_OTHER, _("Other")),
]

# Platform status choices
PLATFORM_STATUS_OPERATIONAL = "operational"
PLATFORM_STATUS_DEGRADED = "degraded"
PLATFORM_STATUS_PARTIAL_OUTAGE = "partial_outage"
PLATFORM_STATUS_MAJOR_OUTAGE = "major_outage"
PLATFORM_STATUS_MAINTENANCE = "maintenance"
PLATFORM_STATUS_CHOICES = [
    (PLATFORM_STATUS_OPERATIONAL, _("Operational")),
    (PLATFORM_STATUS_DEGRADED, _("Degraded Performance")),
    (PLATFORM_STATUS_PARTIAL_OUTAGE, _("Partial Outage")),
    (PLATFORM_STATUS_MAJOR_OUTAGE, _("Major Outage")),
    (PLATFORM_STATUS_MAINTENANCE, _("Under Maintenance")),
]

# Platform components
COMPONENT_API = "api"
COMPONENT_DATABASE = "database"
COMPONENT_QUEUE = "queue_system"
COMPONENT_BOOKING = "booking_system"
COMPONENT_PAYMENT = "payment_system"
COMPONENT_NOTIFICATION = "notification_system"
COMPONENT_CHOICES = [
    (COMPONENT_API, _("API")),
    (COMPONENT_DATABASE, _("Database")),
    (COMPONENT_QUEUE, _("Queue System")),
    (COMPONENT_BOOKING, _("Booking System")),
    (COMPONENT_PAYMENT, _("Payment System")),
    (COMPONENT_NOTIFICATION, _("Notification System")),
]

# Maintenance status choices
MAINTENANCE_SCHEDULED = "scheduled"
MAINTENANCE_IN_PROGRESS = "in_progress"
MAINTENANCE_COMPLETED = "completed"
MAINTENANCE_CANCELLED = "cancelled"
MAINTENANCE_STATUS_CHOICES = [
    (MAINTENANCE_SCHEDULED, _("Scheduled")),
    (MAINTENANCE_IN_PROGRESS, _("In Progress")),
    (MAINTENANCE_COMPLETED, _("Completed")),
    (MAINTENANCE_CANCELLED, _("Cancelled")),
]

# Audit log actions
AUDIT_ACTION_CREATE = "create"
AUDIT_ACTION_UPDATE = "update"
AUDIT_ACTION_DELETE = "delete"
AUDIT_ACTION_VIEW = "view"
AUDIT_ACTION_LOGIN = "login"
AUDIT_ACTION_LOGOUT = "logout"
AUDIT_ACTION_VERIFY = "verify"
AUDIT_ACTION_REJECT = "reject"
AUDIT_ACTION_CHOICES = [
    (AUDIT_ACTION_CREATE, _("Create")),
    (AUDIT_ACTION_UPDATE, _("Update")),
    (AUDIT_ACTION_DELETE, _("Delete")),
    (AUDIT_ACTION_VIEW, _("View")),
    (AUDIT_ACTION_LOGIN, _("Login")),
    (AUDIT_ACTION_LOGOUT, _("Logout")),
    (AUDIT_ACTION_VERIFY, _("Verify")),
    (AUDIT_ACTION_REJECT, _("Reject")),
]
