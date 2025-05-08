from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.companiesapp.models import Company
from apps.queueMeAdminApp.models import (
    AdminNotification,
    AuditLog,
    MaintenanceSchedule,
    PlatformStatus,
    SupportMessage,
    SupportTicket,
    SystemSetting,
    VerificationRequest,
)
from apps.shopapp.models import Shop

User = get_user_model()


class SystemSettingModelTest(TestCase):
    """Test the SystemSetting model"""

    def setUp(self):
        self.setting = SystemSetting.objects.create(
            key="TEST_KEY",
            value="test value",
            description="Test description",
            category="general",
            is_public=True,
        )

    def test_string_representation(self):
        self.assertEqual(str(self.setting), "TEST_KEY: test value")

    def test_ordering(self):
        SystemSetting.objects.create(
            key="ANOTHER_KEY", value="another value", category="security"
        )

        settings = list(SystemSetting.objects.all())
        # 'general' should come before 'security' in alphabetical order
        self.assertEqual(settings[0].key, "TEST_KEY")
        self.assertEqual(settings[1].key, "ANOTHER_KEY")


class AdminNotificationModelTest(TestCase):
    """Test the AdminNotification model"""

    def setUp(self):
        self.notification = AdminNotification.objects.create(
            title="Test Notification",
            message="This is a test notification",
            level="info",
        )

    def test_string_representation(self):
        self.assertEqual(str(self.notification), "Test Notification")

    def test_ordering(self):
        # Create an older notification
        older = AdminNotification.objects.create(
            title="Older Notification",
            message="This is an older notification",
            level="warning",
        )

        # Manually set the created_at to be older
        older.created_at = timezone.now() - timedelta(days=1)
        older.save()

        # Create a newer notification
        newer = AdminNotification.objects.create(
            title="Newer Notification",
            message="This is a newer notification",
            level="error",
        )

        notifications = list(AdminNotification.objects.all())
        # Newest should be first due to ordering
        self.assertEqual(notifications[0].title, "Newer Notification")
        self.assertEqual(notifications[1].title, "Test Notification")
        self.assertEqual(notifications[2].title, "Older Notification")


class VerificationRequestModelTest(TestCase):
    """Test the VerificationRequest model"""

    def setUp(self):
        # Create a user for company
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create a company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Create a shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create verification request
        self.verification = VerificationRequest.objects.create(
            shop=self.shop, status="pending", documents=["doc1.pdf", "doc2.pdf"]
        )

    def test_string_representation(self):
        self.assertEqual(str(self.verification), "Test Shop - Pending")

    def test_unique_pending_constraint(self):
        # Attempting to create another pending request for the same shop should fail
        with self.assertRaises(Exception):
            VerificationRequest.objects.create(shop=self.shop, status="pending")

        # But we can create one with a different status
        VerificationRequest.objects.create(shop=self.shop, status="rejected")


class SupportTicketModelTest(TestCase):
    """Test the SupportTicket model"""

    def setUp(self):
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        self.ticket = SupportTicket.objects.create(
            subject="Test Ticket",
            description="This is a test ticket",
            created_by=self.user,
            category="technical",
        )

    def test_string_representation(self):
        self.assertEqual(
            str(self.ticket), f"{self.ticket.reference_number} - Test Ticket"
        )

    def test_reference_number_generation(self):
        # Verify reference number was generated
        self.assertIsNotNone(self.ticket.reference_number)
        self.assertTrue(self.ticket.reference_number.startswith("TKT-"))

        # Create another ticket and check for unique reference number
        another_ticket = SupportTicket.objects.create(
            subject="Another Ticket",
            description="This is another ticket",
            created_by=self.user,
            category="account",
        )

        self.assertNotEqual(
            self.ticket.reference_number, another_ticket.reference_number
        )


class SupportMessageModelTest(TestCase):
    """Test the SupportMessage model"""

    def setUp(self):
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        self.ticket = SupportTicket.objects.create(
            subject="Test Ticket",
            description="This is a test ticket",
            created_by=self.user,
            category="technical",
        )

        self.message = SupportMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message="This is a test message",
            is_from_admin=False,
        )

    def test_string_representation(self):
        expected = (
            f"{self.ticket.reference_number} - {self.user} - {self.message.created_at}"
        )
        self.assertEqual(str(self.message), expected)

    def test_ordering(self):
        # Create an older message
        older = SupportMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message="Older message",
            is_from_admin=False,
        )

        # Manually set created_at to be older
        older.created_at = timezone.now() - timedelta(hours=1)
        older.save()

        # Create a newer message
        newer = SupportMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message="Newer message",
            is_from_admin=False,
        )

        messages = list(SupportMessage.objects.all())
        # Oldest should be first due to ordering
        self.assertEqual(messages[0].message, "Older message")
        self.assertEqual(messages[1].message, "This is a test message")
        self.assertEqual(messages[2].message, "Newer message")


class PlatformStatusModelTest(TestCase):
    """Test the PlatformStatus model"""

    def setUp(self):
        self.status = PlatformStatus.objects.create(
            component="api",
            status="operational",
            description="API is working normally",
            metrics={"response_time": 120, "error_rate": 0.01},
        )

    def test_string_representation(self):
        self.assertEqual(str(self.status), "API - Operational")

    def test_unique_component(self):
        # Attempting to create another status for the same component should fail
        with self.assertRaises(Exception):
            PlatformStatus.objects.create(component="api", status="degraded")


class MaintenanceScheduleModelTest(TestCase):
    """Test the MaintenanceSchedule model"""

    def setUp(self):
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        self.maintenance = MaintenanceSchedule.objects.create(
            title="Test Maintenance",
            description="This is a test maintenance",
            affected_components=["api", "database"],
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.user,
        )

    def test_string_representation(self):
        expected = f"Test Maintenance ({self.maintenance.start_time.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(self.maintenance), expected)

    def test_ordering(self):
        # Create an earlier scheduled maintenance
        earlier = MaintenanceSchedule.objects.create(
            title="Earlier Maintenance",
            description="This is an earlier maintenance",
            affected_components=["database"],
            start_time=timezone.now() + timedelta(hours=12),
            end_time=timezone.now() + timedelta(hours=14),
            created_by=self.user,
        )

        # Create a later scheduled maintenance
        later = MaintenanceSchedule.objects.create(
            title="Later Maintenance",
            description="This is a later maintenance",
            affected_components=["api"],
            start_time=timezone.now() + timedelta(days=2),
            end_time=timezone.now() + timedelta(days=2, hours=2),
            created_by=self.user,
        )

        maintenances = list(MaintenanceSchedule.objects.all())
        # Latest should be first due to ordering
        self.assertEqual(maintenances[0].title, "Later Maintenance")
        self.assertEqual(maintenances[1].title, "Test Maintenance")
        self.assertEqual(maintenances[2].title, "Earlier Maintenance")


class AuditLogModelTest(TestCase):
    """Test the AuditLog model"""

    def setUp(self):
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        self.log = AuditLog.objects.create(
            action="create",
            actor=self.user,
            entity_type="Shop",
            entity_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"},
        )

    def test_string_representation(self):
        self.assertEqual(
            str(self.log), f"Create Shop {self.log.entity_id} by {self.user}"
        )

    def test_ordering(self):
        # Create an older log
        older = AuditLog.objects.create(
            action="update",
            actor=self.user,
            entity_type="Shop",
            entity_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "new_value"},
        )

        # Manually set timestamp to be older
        older.timestamp = timezone.now() - timedelta(days=1)
        older.save()

        # Create a newer log
        newer = AuditLog.objects.create(
            action="delete",
            actor=self.user,
            entity_type="Shop",
            entity_id="123e4567-e89b-12d3-a456-426614174000",
        )

        logs = list(AuditLog.objects.all())
        # Newest should be first due to ordering
        self.assertEqual(logs[0].action, "delete")
        self.assertEqual(logs[1].action, "create")
        self.assertEqual(logs[2].action, "update")
