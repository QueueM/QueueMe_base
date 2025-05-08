
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

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
from apps.shopapp.models import Shop

User = get_user_model()


class AdminViewsTestCase(TestCase):
    """Test for Admin API Views"""

    def setUp(self):
        self.client = APIClient()

        # Create an admin user
        self.admin = User.objects.create_user(
            phone_number="9876543210",
            password="adminpassword",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

        # Create a regular user
        self.user = User.objects.create_user(
            phone_number="1234567890", password="userpassword", user_type="customer"
        )

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

        # Authenticate admin
        self.client.force_authenticate(user=self.admin)

        # Create test data
        self.system_setting = SystemSetting.objects.create(
            key="TEST_KEY", value="test value", category="general"
        )

        self.notification = AdminNotification.objects.create(
            title="Test Notification", message="Test message", level="info"
        )

        self.verification_request = VerificationRequest.objects.create(
            shop=self.shop, status="pending"
        )

        self.support_ticket = SupportTicket.objects.create(
            subject="Test Ticket",
            description="Test description",
            created_by=self.user,
            category="technical",
        )

        self.support_message = SupportMessage.objects.create(
            ticket=self.support_ticket, sender=self.user, message="Test message"
        )

        self.platform_status = PlatformStatus.objects.create(
            component="api", status="operational", description="API is working normally"
        )

        self.maintenance = MaintenanceSchedule.objects.create(
            title="Test Maintenance",
            description="Test description",
            affected_components=["api"],
            start_time="2025-01-01T10:00:00Z",
            end_time="2025-01-01T12:00:00Z",
            created_by=self.admin,
        )

    def test_system_settings_list(self):
        """Test getting list of system settings"""
        url = reverse("systemsetting-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_system_settings_create(self):
        """Test creating a system setting"""
        url = reverse("systemsetting-list")
        data = {
            "key": "NEW_KEY",
            "value": "new value",
            "category": "security",
            "description": "New description",
            "is_public": True,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SystemSetting.objects.count(), 2)

    def test_system_settings_update(self):
        """Test updating a system setting"""
        url = reverse("systemsetting-detail", args=[self.system_setting.id])
        data = {
            "key": "TEST_KEY",
            "value": "updated value",
            "category": "general",
            "description": "Updated description",
            "is_public": True,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.system_setting.refresh_from_db()
        self.assertEqual(self.system_setting.value, "updated value")
        self.assertEqual(self.system_setting.description, "Updated description")

    def test_system_settings_public(self):
        """Test getting public settings"""
        # Create a public setting
        SystemSetting.objects.create(
            key="PUBLIC_KEY", value="public value", category="general", is_public=True
        )

        url = reverse("systemsetting-public")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Only the public one

    def test_admin_notifications_list(self):
        """Test getting list of admin notifications"""
        url = reverse("adminnotification-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_notifications_mark_read(self):
        """Test marking a notification as read"""
        url = reverse("adminnotification-mark-read", args=[self.notification.id])
        response = self.client.patch(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_admin_notifications_mark_all_read(self):
        """Test marking all notifications as read"""
        # Create another notification
        AdminNotification.objects.create(
            title="Another Notification", message="Another message", level="warning"
        )

        url = reverse("adminnotification-mark-all-read")
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AdminNotification.objects.filter(is_read=True).count(), 2)

    def test_verification_requests_list(self):
        """Test getting list of verification requests"""
        url = reverse("verificationrequest-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_verification_requests_pending(self):
        """Test getting pending verification requests"""
        url = reverse("verificationrequest-pending")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_verification_requests_verify(self):
        """Test verifying a request"""
        url = reverse("verificationrequest-verify", args=[self.verification_request.id])
        data = {"action": "approve", "notes": "Approved by tests"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.verification_request.refresh_from_db()
        self.assertEqual(self.verification_request.status, "approved")

        # Check shop was verified
        self.shop.refresh_from_db()
        self.assertTrue(self.shop.is_verified)

    def test_support_tickets_list(self):
        """Test getting list of support tickets"""
        url = reverse("supportticket-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_support_tickets_assign(self):
        """Test assigning a ticket"""
        url = reverse("supportticket-assign", args=[self.support_ticket.id])
        data = {"admin_id": str(self.admin.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.support_ticket.refresh_from_db()
        self.assertEqual(self.support_ticket.assigned_to, self.admin)
        self.assertEqual(self.support_ticket.status, "in_progress")

    def test_support_tickets_change_status(self):
        """Test changing ticket status"""
        url = reverse("supportticket-change-status", args=[self.support_ticket.id])
        data = {"status": "resolved"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.support_ticket.refresh_from_db()
        self.assertEqual(self.support_ticket.status, "resolved")

    def test_support_messages_list(self):
        """Test getting list of support messages"""
        url = reverse("supportmessage-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_support_messages_filter_by_ticket(self):
        """Test filtering messages by ticket"""
        url = reverse("supportmessage-list")
        response = self.client.get(url, {"ticket": self.support_ticket.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_support_messages_create(self):
        """Test creating a support message"""
        url = reverse("supportmessage-list")
        data = {
            "ticket": str(self.support_ticket.id),
            "message": "Response from admin",
            "is_internal_note": False,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportMessage.objects.count(), 2)

        # Verify message was created with correct attributes
        message = SupportMessage.objects.latest("created_at")
        self.assertEqual(message.sender, self.admin)
        self.assertEqual(message.is_from_admin, True)

    def test_platform_status_list(self):
        """Test getting list of platform statuses"""
        url = reverse("platformstatus-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_platform_status_overall(self):
        """Test getting overall platform status"""
        url = reverse("platformstatus-overall")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "operational")

    def test_maintenance_schedule_list(self):
        """Test getting list of maintenance schedules"""
        url = reverse("maintenanceschedule-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_maintenance_schedule_upcoming(self):
        """Test getting upcoming maintenance schedules"""
        url = reverse("maintenanceschedule-upcoming")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_maintenance_schedule_cancel(self):
        """Test cancelling a maintenance schedule"""
        url = reverse("maintenanceschedule-cancel", args=[self.maintenance.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, "cancelled")

    def test_system_overview(self):
        """Test getting system overview"""
        url = reverse("system-overview")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_shops", response.data)
        self.assertIn("total_users", response.data)
        self.assertIn("pending_verifications", response.data)
        self.assertIn("system_health", response.data)

    def test_system_health(self):
        """Test system health endpoint (public access)"""
        # Log out admin
        self.client.logout()

        url = reverse("system-health")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)
        self.assertIn("timestamp", response.data)
        self.assertIn("database", response.data)
