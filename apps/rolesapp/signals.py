# apps/rolesapp/signals.py
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.rolesapp.models import Role, UserRole
from apps.rolesapp.services.permission_resolver import PermissionResolver
from apps.rolesapp.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Role)
def role_saved(sender, instance, created, **kwargs):
    """
    Signal handler for role creation/updates

    Invalidates permission cache when a role is saved.
    """
    # Invalidate cache for users with this role
    user_ids = UserRole.objects.filter(role=instance).values_list("user_id", flat=True)
    for user_id in user_ids:
        PermissionResolver.invalidate_permission_cache(user_id=user_id)


@receiver(post_delete, sender=Role)
def role_deleted(sender, instance, **kwargs):
    """
    Signal handler for role deletion

    Invalidates permission cache when a role is deleted.
    """
    # Invalidate all permission cache
    PermissionResolver.invalidate_permission_cache()


@receiver(post_save, sender=UserRole)
def user_role_saved(sender, instance, created, **kwargs):
    """
    Signal handler for user role creation/updates

    Invalidates permission cache for the user.
    """
    PermissionResolver.invalidate_permission_cache(user_id=instance.user_id)


@receiver(post_delete, sender=UserRole)
def user_role_deleted(sender, instance, **kwargs):
    """
    Signal handler for user role deletion

    Invalidates permission cache for the user.
    """
    PermissionResolver.invalidate_permission_cache(user_id=instance.user_id)


# We don't want to run these signals during test
if not settings.TESTING:
    # Shop entity signals
    try:
        from apps.shopapp.models import Shop

        @receiver(post_save, sender=Shop)
        def shop_saved(sender, instance, created, **kwargs):
            """
            Create default roles for a new shop
            """
            if created:
                try:
                    # Only create default roles for a new shop
                    content_type = ContentType.objects.get(
                        app_label="apps", model="shop"
                    )

                    # Check if roles already exist
                    existing_roles = Role.objects.filter(
                        content_type=content_type, object_id=instance.id
                    ).exists()

                    if not existing_roles:
                        logger.info(f"Creating default roles for shop {instance.name}")
                        PermissionService.create_default_roles_for_entity(
                            instance, "shop"
                        )

                        # Assign shop manager role to shop manager if one exists
                        if instance.manager:
                            manager_role = Role.objects.get(
                                content_type=content_type,
                                object_id=instance.id,
                                role_type="shop_manager",
                            )

                            PermissionService.assign_role_to_user(
                                instance.manager, manager_role, is_primary=True
                            )
                except Exception as e:
                    logger.error(f"Error creating default roles for shop: {e}")

    except ImportError:
        pass  # Shop model not available yet

    # Company entity signals
    try:
        from apps.companiesapp.models import Company

        @receiver(post_save, sender=Company)
        def company_saved(sender, instance, created, **kwargs):
            """
            Create default roles for a new company
            """
            if created:
                try:
                    # Only create default roles for a new company
                    content_type = ContentType.objects.get(
                        app_label="apps", model="company"
                    )

                    # Check if roles already exist
                    existing_roles = Role.objects.filter(
                        content_type=content_type, object_id=instance.id
                    ).exists()

                    if not existing_roles:
                        logger.info(
                            f"Creating default roles for company {instance.name}"
                        )
                        roles = PermissionService.create_default_roles_for_entity(
                            instance, "company"
                        )

                        # Assign company owner role to owner
                        if "owner" in roles and instance.owner:
                            PermissionService.assign_role_to_user(
                                instance.owner, roles["owner"], is_primary=True
                            )
                except Exception as e:
                    logger.error(f"Error creating default roles for company: {e}")

    except ImportError:
        pass  # Company model not available yet
