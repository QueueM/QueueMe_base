from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.companiesapp.models import Company
from apps.queueMeAdminApp.models import (
    AdminNotification,
    MaintenanceSchedule,
    PlatformStatus,
    SupportMessage,
    SupportTicket,
    SystemSetting,
    VerificationRequest,
)
from apps.queueMeAdminApp.services.admin_service import AdminService
from apps.queueMeAdminApp.services.monitoring_service import MonitoringService
from apps.queueMeAdminApp.services.settings_service import SettingsService
from apps.queueMeAdminApp.services.support_service import SupportService
from apps.queueMeAdminApp.services.verification_service import VerificationService
from apps.shopapp.models import Shop

User = get_user_model()


class AdminServiceTest(TestCase):
    """Test the AdminService"""

    def setUp(self):
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

    def test_log_audit(self):
        """Test logging an audit event"""
        log = AdminService.log_audit(
            self.user,
            "create",
            "Shop",
            "123e4567-e89b-12d3-a456-426614174000",
            {"name": "Test Shop"},
        )

        self.assertEqual(log.action, "create")
        self.assertEqual(log.entity_type, "Shop")
        self.assertEqual(log.entity_id, "123e4567-e89b-12d3-a456-426614174000")
        self.assertEqual(log.details, {"name": "Test Shop"})
        self.assertEqual(log.actor, self.user)

    def test_create_notification(self):
        """Test creating an admin notification"""
        notification = AdminService.create_notification(
            "Test Notification", "This is a test notification", "info", {"key": "value"}
        )

        self.assertEqual(notification.title, "Test Notification")
        self.assertEqual(notification.message, "This is a test notification")
        self.assertEqual(notification.level, "info")
        self.assertEqual(notification.data, {"key": "value"})
        self.assertFalse(notification.is_read)

    def test_get_system_setting(self):
        """Test getting a system setting"""
        # Create a setting
        SystemSetting.objects.create(key="TEST_KEY", value="test value")

        # Get the setting
        value = AdminService.get_system_setting("TEST_KEY")
        self.assertEqual(value, "test value")

        # Test default value for non-existent setting
        value = AdminService.get_system_setting("NON_EXISTENT", "default value")
        self.assertEqual(value, "default value")

    def test_update_system_setting(self):
        """Test updating a system setting"""
        # Create a setting
        setting = AdminService.update_system_setting(
            "TEST_KEY", "test value", "general", "Test description", True
        )

        self.assertEqual(setting.key, "TEST_KEY")
        self.assertEqual(setting.value, "test value")
        self.assertEqual(setting.category, "general")
        self.assertEqual(setting.description, "Test description")
        self.assertTrue(setting.is_public)

        # Update the setting
        setting = AdminService.update_system_setting("TEST_KEY", "new value")

        self.assertEqual(setting.value, "new value")
        # Other fields should remain unchanged
        self.assertEqual(setting.category, "general")
        self.assertEqual(setting.description, "Test description")
        self.assertTrue(setting.is_public)


class VerificationServiceTest(TestCase):
    """Test the VerificationService"""

    def setUp(self):
        # Create a user for company
        self.owner = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create a company
        self.company = Company.objects.create(
            name="Test Company", owner=self.owner, contact_phone="1234567890"
        )

        # Create a shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create an admin user
        self.admin = User.objects.create(phone_number="9876543210", user_type="admin")

        # Create a shop manager
        self.manager = User.objects.create(
            phone_number="5555555555", user_type="employee", email="manager@example.com"
        )

        # Set manager for shop
        self.shop.manager = self.manager
        self.shop.save()

    def test_create_verification_request(self):
        """Test creating a verification request"""
        request = VerificationService.create_verification_request(
            self.shop, ["doc1.pdf", "doc2.pdf"]
        )

        self.assertEqual(request.shop, self.shop)
        self.assertEqual(request.status, "pending")
        self.assertEqual(request.documents, ["doc1.pdf", "doc2.pdf"])

        # Test that creating another pending request returns the existing one
        request2 = VerificationService.create_verification_request(self.shop)
        self.assertEqual(request.id, request2.id)

    def test_approve_verification(self):
        """Test approving a verification request"""
        # Create a verification request
        request = VerificationRequest.objects.create(shop=self.shop, status="pending")

        # Approve the request
        updated = VerificationService.approve_verification(request, self.admin, "Approved")

        # Check request was updated
        self.assertEqual(updated.status, "approved")
        self.assertEqual(updated.verified_by, self.admin)
        self.assertEqual(updated.notes, "Approved")
        self.assertIsNotNone(updated.verified_at)

        # Check shop was updated
        self.shop.refresh_from_db()
        self.assertTrue(self.shop.is_verified)
        self.assertIsNotNone(self.shop.verification_date)

    def test_reject_verification(self):
        """Test rejecting a verification request"""
        # Create a verification request
        request = VerificationRequest.objects.create(shop=self.shop, status="pending")

        # Reject the request
        updated = VerificationService.reject_verification(
            request, self.admin, "Invalid documents", "Rejected"
        )

        # Check request was updated
        self.assertEqual(updated.status, "rejected")
        self.assertEqual(updated.verified_by, self.admin)
        self.assertEqual(updated.rejection_reason, "Invalid documents")
        self.assertEqual(updated.notes, "Rejected")
        self.assertIsNotNone(updated.verified_at)

        # Check shop was not verified
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_verified)
        self.assertIsNone(self.shop.verification_date)

    def test_send_verification_email(self):
        """Test sending verification emails"""
        # Create a verification request
        request = VerificationRequest.objects.create(shop=self.shop, status="pending")

        # Approve and send email
        VerificationService.approve_verification(request, self.admin, "Approved")

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.manager.email])
        self.assertIn("verified", mail.outbox[0].subject)


class SupportServiceTest(TestCase):
    """Test the SupportService"""

    def setUp(self):
        # Create a customer
        self.customer = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create an admin
        self.admin = User.objects.create(phone_number="9876543210", user_type="admin")

        # Create a support ticket
        self.ticket = SupportTicket.objects.create(
            subject="Test Ticket",
            description="This is a test ticket",
            created_by=self.customer,
            category="technical",
        )

    def test_create_ticket(self):
        """Test creating a support ticket"""
        ticket = SupportService.create_ticket(
            "New Ticket", "This is a new ticket", self.customer, "account", "high"
        )

        self.assertEqual(ticket.subject, "New Ticket")
        self.assertEqual(ticket.description, "This is a new ticket")
        self.assertEqual(ticket.created_by, self.customer)
        self.assertEqual(ticket.category, "account")
        self.assertEqual(ticket.priority, "high")
        self.assertEqual(ticket.status, "open")

        # Check that an initial message was created
        messages = SupportMessage.objects.filter(ticket=ticket)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().message, "This is a new ticket")
        self.assertEqual(messages.first().sender, self.customer)

        # Check that a notification was created
        notifications = AdminNotification.objects.filter(title__contains=ticket.reference_number)
        self.assertEqual(notifications.count(), 1)

    def test_assign_ticket(self):
        """Test assigning a ticket to an admin"""
        updated = SupportService.assign_ticket(self.ticket, self.admin, self.admin)

        self.assertEqual(updated.assigned_to, self.admin)
        self.assertEqual(updated.status, "in_progress")

        # Check that a message was created
        messages = SupportMessage.objects.filter(ticket=self.ticket, is_internal_note=True)
        self.assertEqual(messages.count(), 1)
        self.assertIn("assigned to", messages.first().message)

    def test_update_ticket_status(self):
        """Test updating a ticket's status"""
        updated = SupportService.update_ticket_status(self.ticket, "resolved", self.admin)

        self.assertEqual(updated.status, "resolved")

        # Check that a message was created
        messages = SupportMessage.objects.filter(ticket=self.ticket, is_internal_note=True)
        self.assertEqual(messages.count(), 1)
        self.assertIn("status changed", messages.first().message)

    def test_update_ticket_on_new_message(self):
        """Test updating ticket status when a new message is added"""
        # Set ticket status to waiting for customer
        self.ticket.status = "waiting_for_customer"
        self.ticket.save()

        # Add a message from admin
        SupportMessage.objects.create(
            ticket=self.ticket,
            sender=self.admin,
            message="Admin response",
            is_from_admin=True,
        )

        # Update ticket
        updated = SupportService.update_ticket_on_new_message(self.ticket.id, self.admin)

        # Status should be updated to in progress
        self.assertEqual(updated.status, "in_progress")


class MonitoringServiceTest(TestCase):
    """Test the MonitoringService"""

    def setUp(self):
        # Create some platform statuses
        self.api_status = PlatformStatus.objects.create(
            component="api", status="operational", description="API is working normally"
        )

        self.db_status = PlatformStatus.objects.create(
            component="database",
            status="operational",
            description="Database is working normally",
        )

        # Create a user for maintenance
        self.admin = User.objects.create(phone_number="9876543210", user_type="admin")

    def test_get_overall_status(self):
        """Test getting overall platform status"""
        status = MonitoringService.get_overall_status()

        self.assertEqual(status["status"], "operational")
        self.assertEqual(len(status["components"]), 2)
        self.assertFalse("active_maintenance" in status)

        # Update one component to degraded
        self.api_status.status = "degraded"
        self.api_status.save()

        status = MonitoringService.get_overall_status()
        self.assertEqual(status["status"], "degraded")

    def test_cancel_maintenance(self):
        """Test cancelling a scheduled maintenance"""
        # Create a maintenance
        maintenance = MaintenanceSchedule.objects.create(
            title="Test Maintenance",
            description="This is a test maintenance",
            affected_components=["api", "database"],
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.admin,
        )

        # Cancel the maintenance
        updated = MonitoringService.cancel_maintenance(maintenance, self.admin)

        self.assertEqual(updated.status, "cancelled")
        self.assertIn("CANCELLED", updated.description)

        # Check that a notification was created
        notifications = AdminNotification.objects.filter(title__contains="cancelled")
        self.assertEqual(notifications.count(), 1)

    def test_get_basic_health_check(self):
        """Test getting basic health check"""
        health = MonitoringService.get_basic_health_check()

        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["database"], "connected")
        self.assertIn("checks", health)


class SettingsServiceTest(TestCase):
    """Test the SettingsService"""

    def setUp(self):
        # Create a setting
        self.setting = SystemSetting.objects.create(
            key="TEST_KEY",
            value="test value",
            category="general",
            description="Test description",
            is_public=True,
        )

    def test_get_setting(self):
        """Test getting a setting"""
        value = SettingsService.get_setting("TEST_KEY")
        self.assertEqual(value, "test value")

        # Test default value for non-existent setting
        value = SettingsService.get_setting("NON_EXISTENT", "default value")
        self.assertEqual(value, "default value")

    def test_set_setting(self):
        """Test setting a setting"""
        setting = SettingsService.set_setting(
            "NEW_KEY", "new value", "security", "New description", False
        )

        self.assertEqual(setting.key, "NEW_KEY")
        self.assertEqual(setting.value, "new value")
        self.assertEqual(setting.category, "security")
        self.assertEqual(setting.description, "New description")
        self.assertFalse(setting.is_public)

        # Update existing setting
        setting = SettingsService.set_setting("TEST_KEY", "updated value")

        self.assertEqual(setting.value, "updated value")
        # Other fields should remain unchanged
        self.assertEqual(setting.category, "general")
        self.assertEqual(setting.description, "Test description")
        self.assertTrue(setting.is_public)

    def test_delete_setting(self):
        """Test deleting a setting"""
        result = SettingsService.delete_setting("TEST_KEY")
        self.assertTrue(result)

        # Setting should be deleted
        with self.assertRaises(SystemSetting.DoesNotExist):
            SystemSetting.objects.get(key="TEST_KEY")

        # Deleting a non-existent setting should return False
        result = SettingsService.delete_setting("NON_EXISTENT")
        self.assertFalse(result)

    def test_get_all_settings(self):
        """Test getting all settings"""
        # Create a few more settings
        SystemSetting.objects.create(
            key="PUBLIC_KEY", value="public value", category="general", is_public=True
        )

        SystemSetting.objects.create(
            key="PRIVATE_KEY",
            value="private value",
            category="security",
            is_public=False,
        )

        # Get all settings
        settings = SettingsService.get_all_settings()
        self.assertEqual(len(settings), 3)

        # Get settings by category
        settings = SettingsService.get_all_settings(category="security")
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings["PRIVATE_KEY"], "private value")

        # Get public settings only
        settings = SettingsService.get_all_settings(public_only=True)
        self.assertEqual(len(settings), 2)
        self.assertIn("TEST_KEY", settings)
        self.assertIn("PUBLIC_KEY", settings)
        self.assertNotIn("PRIVATE_KEY", settings)
