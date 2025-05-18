# apps/rolesapp/constants.py
from django.utils.translation import gettext_lazy as _

# Permission Constants
RESOURCE_HIERARCHY = {
    "shop": 10,
    "service": 20,
    "employee": 30,
    "specialist": 40,
    "customer": 50,
    "booking": 60,
    "queue": 70,
    "report": 80,
    "reel": 90,
    "story": 100,
    "chat": 110,
    "payment": 120,
    "subscription": 130,
    "discount": 140,
    "review": 150,
    "package": 160,
    "category": 170,
    "company": 180,
    "roles": 190,
    "notifications": 200,
    "ad": 210,
    "analytics": 220,
}

ACTION_HIERARCHY = {
    "view": 10,
    "add": 20,
    "edit": 30,
    "delete": 40,
    "manage": 50,
    "approve": 60,
    "report": 70,
}

# Role Hierarchy (higher is more powerful)
ROLE_HIERARCHY = {
    "queue_me_admin": 1000,
    "queue_me_employee": 900,
    "company": 800,
    "shop_manager": 700,
    "shop_employee": 600,
    "custom": 500,
}

# Default Role Weights
DEFAULT_WEIGHTS = {
    "queue_me_admin": 1000,
    "queue_me_employee": 800,
    "company": 600,
    "shop_manager": 400,
    "shop_employee": 200,
    "custom": 100,
}

# Permission mappings for default roles
DEFAULT_ROLE_PERMISSIONS = {
    "queue_me_admin": [
        # Admin has all permissions
        {"resource": "*", "action": "*"},
    ],
    "queue_me_employee": [
        # Basic view permissions for everything
        {"resource": "*", "action": "view"},
        # Managing customer support
        {"resource": "customer", "action": "*"},
        {"resource": "chat", "action": "*"},
        {"resource": "review", "action": "*"},
        # Analytics and reporting
        {"resource": "analytics", "action": "*"},
        {"resource": "report", "action": "*"},
    ],
    "company": [
        # Company can manage all its shops
        {"resource": "shop", "action": "*"},
        {"resource": "employee", "action": "*"},
        {"resource": "specialist", "action": "*"},
        {"resource": "service", "action": "*"},
        {"resource": "package", "action": "*"},
        {"resource": "booking", "action": "*"},
        {"resource": "queue", "action": "*"},
        {"resource": "reel", "action": "*"},
        {"resource": "story", "action": "*"},
        {"resource": "review", "action": "view"},
        {"resource": "analytics", "action": "view"},
        {"resource": "report", "action": "view"},
        {"resource": "roles", "action": "*"},
    ],
    "shop_manager": [
        # Shop manager can manage their own shop
        {"resource": "employee", "action": "*"},
        {"resource": "specialist", "action": "*"},
        {"resource": "service", "action": "*"},
        {"resource": "package", "action": "*"},
        {"resource": "booking", "action": "*"},
        {"resource": "queue", "action": "*"},
        {"resource": "reel", "action": "*"},
        {"resource": "story", "action": "*"},
        {"resource": "review", "action": "view"},
        {"resource": "chat", "action": "*"},
        {"resource": "roles", "action": "*"},
        {"resource": "analytics", "action": "view"},
        {"resource": "report", "action": "view"},
    ],
    "shop_employee": [
        # Base employee can view most things but limited editing
        {"resource": "service", "action": "view"},
        {"resource": "package", "action": "view"},
        {"resource": "booking", "action": "view"},
        {"resource": "booking", "action": "edit"},
        {"resource": "queue", "action": "view"},
        {"resource": "queue", "action": "edit"},
        {"resource": "customer", "action": "view"},
        {"resource": "chat", "action": "view"},
        {"resource": "chat", "action": "add"},
    ],
}

# Role-specific constants
SYSTEM_ROLES = [
    "queue_me_admin",
    "queue_me_employee",
    "company",
    "shop_manager",
]

# Context types for permissions
PERMISSION_CONTEXTS = {
    "global": "global",  # System-wide permission
    "company": "company",  # Company-specific
    "shop": "shop",  # Shop-specific
}

# Permission denied messages
PERMISSION_DENIED_MESSAGES = {
    "view": _("You don't have permission to view this resource."),
    "add": _("You don't have permission to add this resource."),
    "edit": _("You don't have permission to edit this resource."),
    "delete": _("You don't have permission to delete this resource."),
    "manage": _("You don't have permission to manage this resource."),
    "approve": _("You don't have permission to approve this resource."),
    "report": _("You don't have permission to report on this resource."),
    "default": _("Permission denied."),
}
