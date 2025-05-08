from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.notificationsapp.services.notification_service import NotificationService

from .models import Employee, EmployeeLeave


@receiver(post_save, sender=Employee)
def employee_created_or_updated(sender, instance, created, **kwargs):
    """Send notification when new employee is created or updated"""
    if created:
        # Set user type to employee
        instance.user.user_type = "employee"
        instance.user.save()

        # Assign default role if roles app is installed
        try:
            from apps.rolesapp.models import Role, UserRole

            # Get default employee role for this shop or create one
            default_role, created = Role.objects.get_or_create(
                role_type="shop_employee",
                shop=instance.shop,
                defaults={"name": "Employee"},
            )

            # Assign role to user
            UserRole.objects.get_or_create(user=instance.user, role=default_role)
        except ImportError:
            # Roles app not installed, skip
            pass


@receiver(post_save, sender=EmployeeLeave)
def employee_leave_status_changed(sender, instance, created, **kwargs):
    """Send notification when leave status changes"""
    if not created and instance.status in ["approved", "rejected"]:
        # Notify employee about leave approval/rejection
        try:
            NotificationService.send_notification(
                user_id=instance.employee.user.id,
                notification_type="leave_status_update",
                data={
                    "leave_id": str(instance.id),
                    "leave_type": instance.get_leave_type_display(),
                    "start_date": instance.start_date.strftime("%d %b, %Y"),
                    "end_date": instance.end_date.strftime("%d %b, %Y"),
                    "status": instance.get_status_display(),
                },
            )
        except ImportError:
            # Notification service not available, skip
            pass


@receiver(pre_delete, sender=Employee)
def remove_employee_role(sender, instance, **kwargs):
    """Remove roles when employee is deleted"""
    try:
        from apps.rolesapp.models import UserRole

        UserRole.objects.filter(user=instance.user).delete()
    except ImportError:
        # Roles app not installed, skip
        pass
