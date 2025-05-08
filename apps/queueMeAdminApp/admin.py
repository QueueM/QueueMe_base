from django.db import transaction

from apps.queueMeAdminApp.models import AdminNotification, AuditLog

from .constants import NOTIFICATION_LEVEL_INFO


class AdminService:
    """
    Service for common admin operations.
    """

    @staticmethod
    def log_audit(user, action, entity_type, entity_id, details=None, ip_address=None):
        """
        Log an admin action to the audit log.

        Args:
            user: The user performing the action
            action: Type of action (e.g., 'create', 'update', 'delete')
            entity_type: Type of entity being acted upon (e.g., 'Shop', 'User')
            entity_id: ID of the entity
            details: Additional details about the action (optional)
            ip_address: IP address of the user (optional)

        Returns:
            AuditLog: The created audit log entry
        """
        return AuditLog.objects.create(
            action=action,
            actor=user,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
        )

    @staticmethod
    def create_notification(title, message, level=NOTIFICATION_LEVEL_INFO, data=None):
        """
        Create a notification for admin users.

        Args:
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error, critical)
            data: Additional data for the notification (optional)

        Returns:
            AdminNotification: The created notification
        """
        return AdminNotification.objects.create(
            title=title, message=message, level=level, data=data or {}
        )

    @staticmethod
    def get_system_setting(key, default=None):
        """
        Get a system setting by key.

        Args:
            key: Setting key
            default: Default value if setting doesn't exist

        Returns:
            The setting value or default
        """
        from ..models import SystemSetting

        try:
            setting = SystemSetting.objects.get(key=key)
            return setting.value
        except SystemSetting.DoesNotExist:
            return default

    @staticmethod
    @transaction.atomic
    def update_system_setting(
        key, value, category=None, description=None, is_public=None
    ):
        """
        Update or create a system setting.

        Args:
            key: Setting key
            value: Setting value
            category: Setting category (optional)
            description: Setting description (optional)
            is_public: Whether the setting is public (optional)

        Returns:
            SystemSetting: The updated or created setting
        """
        from ..models import SystemSetting

        # Standardize key format
        key = key.upper()

        setting, created = SystemSetting.objects.get_or_create(
            key=key,
            defaults={
                "value": value,
                "category": category or "general",
                "description": description or "",
                "is_public": is_public or False,
            },
        )

        if not created:
            # Update existing setting
            setting.value = value

            if category is not None:
                setting.category = category

            if description is not None:
                setting.description = description

            if is_public is not None:
                setting.is_public = is_public

            setting.save()

        return setting
