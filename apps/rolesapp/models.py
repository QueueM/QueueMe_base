# apps/rolesapp/models.py
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class Permission(models.Model):
    """
    Permission model defines granular actions on resources

    Each permission represents an action (view, add, edit, delete)
    that can be performed on a specific resource (shop, service, employee, etc.)
    """

    RESOURCE_CHOICES = (
        ("shop", _("Shop")),
        ("service", _("Service")),
        ("employee", _("Employee")),
        ("specialist", _("Specialist")),
        ("customer", _("Customer")),
        ("booking", _("Booking")),
        ("queue", _("Queue")),
        ("report", _("Report")),
        ("reel", _("Reel")),
        ("story", _("Story")),
        ("chat", _("Chat")),
        ("payment", _("Payment")),
        ("subscription", _("Subscription")),
        ("discount", _("Discount")),
        ("review", _("Review")),
        ("package", _("Package")),
        ("category", _("Category")),
        ("company", _("Company")),
        ("roles", _("Roles")),
        ("notifications", _("Notifications")),
        ("ad", _("Advertisement")),
        ("analytics", _("Analytics")),
    )

    ACTION_CHOICES = (
        ("view", _("View")),
        ("add", _("Add")),
        ("edit", _("Edit")),
        ("delete", _("Delete")),
        ("manage", _("Manage")),
        ("approve", _("Approve")),
        ("report", _("Report")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.CharField(_("Resource"), max_length=50, choices=RESOURCE_CHOICES)
    action = models.CharField(_("Action"), max_length=10, choices=ACTION_CHOICES)
    code_name = models.CharField(
        _("Code Name"), max_length=100, unique=True, blank=True
    )
    description = models.TextField(_("Description"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        unique_together = ("resource", "action")
        ordering = ["resource", "action"]

    def __str__(self):
        return f"{self.get_action_display()} {self.get_resource_display()}"

    def save(self, *args, **kwargs):
        # Auto-generate code_name if not provided
        if not self.code_name:
            self.code_name = f"{self.resource}_{self.action}"
        super().save(*args, **kwargs)


class Role(models.Model):
    """
    Role model defining a set of permissions

    Roles can be system-wide (Queue Me Admin, Company) or tied to a specific
    entity like a Shop. The role_type determines the scope and hierarchy of the role.
    """

    ROLE_TYPE_CHOICES = (
        ("queue_me_admin", _("Queue Me Admin")),
        ("queue_me_employee", _("Queue Me Employee")),
        ("company", _("Company")),
        ("shop_manager", _("Shop Manager")),
        ("shop_employee", _("Shop Employee")),
        ("custom", _("Custom")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    role_type = models.CharField(
        _("Role Type"), max_length=20, choices=ROLE_TYPE_CHOICES
    )
    permissions = models.ManyToManyField(
        Permission, related_name="roles", verbose_name=_("Permissions"), blank=True
    )

    # Generic foreign key for associating roles with any entity
    # Typically used for Shop-specific roles
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Entity Type"),
    )
    object_id = models.UUIDField(null=True, blank=True, verbose_name=_("Entity ID"))
    entity = GenericForeignKey("content_type", "object_id")

    # Role hierarchy (support parent-child relationships for inheritance)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent Role"),
    )

    weight = models.IntegerField(
        _("Weight"),
        default=0,
        help_text=_("Higher weight roles take precedence in conflict resolution"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    is_system = models.BooleanField(
        _("System Role"), default=False, help_text=_("System roles cannot be deleted")
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["-weight", "name"]

    def __str__(self):
        entity_info = f" ({self.entity})" if self.entity else ""
        return f"{self.name}{entity_info}"

    @property
    def all_permissions(self):
        """Get all permissions, including those inherited from parent roles"""
        direct_permissions = set(self.permissions.all())

        if self.parent:
            inherited_permissions = set(self.parent.all_permissions)
            return direct_permissions.union(inherited_permissions)

        return direct_permissions

    def has_permission(self, resource, action):
        """Check if role has a specific permission"""
        return self.permissions.filter(resource=resource, action=action).exists() or (
            self.parent and self.parent.has_permission(resource, action)
        )


class UserRole(models.Model):
    """
    UserRole model for assigning roles to users

    This is the many-to-many relationship between users and roles,
    with additional metadata about when the role was assigned.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "authapp.User",
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name=_("User"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name=_("Role"),
    )
    assigned_at = models.DateTimeField(_("Assigned At"), auto_now_add=True)
    assigned_by = models.ForeignKey(
        "authapp.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
        verbose_name=_("Assigned By"),
    )
    is_primary = models.BooleanField(
        _("Primary Role"),
        default=False,
        help_text=_("If True, this is the user's primary role in this context"),
    )

    class Meta:
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        unique_together = ("user", "role")
        ordering = ["-is_primary", "assigned_at"]

    def __str__(self):
        return f"{self.user.phone_number} - {self.role.name}"

    def save(self, *args, **kwargs):
        # If marking as primary, ensure no other role for this user+entity is primary
        if self.is_primary and self.role.entity:
            UserRole.objects.filter(
                user=self.user,
                role__content_type=self.role.content_type,
                role__object_id=self.role.object_id,
                is_primary=True,
            ).exclude(id=self.id).update(is_primary=False)

        super().save(*args, **kwargs)


class RolePermissionLog(models.Model):
    """Audit log for permission changes to roles"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permission_logs",
        verbose_name=_("Role"),
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_logs",
        verbose_name=_("Permission"),
    )
    action_type = models.CharField(
        _("Action Type"),
        max_length=10,
        choices=(("add", _("Added")), ("remove", _("Removed"))),
    )
    performed_by = models.ForeignKey(
        "authapp.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="permission_change_logs",
        verbose_name=_("Performed By"),
    )
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("Role Permission Log")
        verbose_name_plural = _("Role Permission Logs")
        ordering = ["-timestamp"]

    def __str__(self):
        action = "added to" if self.action_type == "add" else "removed from"
        return f"{self.permission} {action} {self.role} by {self.performed_by} at {self.timestamp}"
