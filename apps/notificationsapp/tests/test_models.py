from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate


class NotificationTemplateTest(TestCase):
    def setUp(self):
        # Create test data
        self.template = NotificationTemplate.objects.create(
            type="appointment_confirmation",
            channel="sms",
            subject="Appointment Confirmation",
            body_en="Your appointment is confirmed for {{date}} at {{time}}.",
            body_ar="تم تأكيد موعدك في {{date}} في {{time}}.",
            variables=["date", "time"],
        )

    def test_template_str_representation(self):
        """Test the string representation of a notification template"""
        self.assertEqual(str(self.template), "Appointment Confirmation - SMS")


class NotificationTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="1234567890", email="test@example.com"
        )

        # Create a template
        self.template = NotificationTemplate.objects.create(
            type="appointment_confirmation",
            channel="sms",
            subject="Appointment Confirmation",
            body_en="Your appointment is confirmed for {{date}} at {{time}}.",
            body_ar="تم تأكيد موعدك في {{date}} في {{time}}.",
            variables=["date", "time"],
        )

        # Create a notification
        self.notification = Notification.objects.create(
            user=self.user,
            template=self.template,
            type="appointment_confirmation",
            channel="sms",
            subject="Appointment Confirmation",
            body="Your appointment is confirmed for 2023-05-01 at 10:00 AM.",
            data={"date": "2023-05-01", "time": "10:00 AM"},
        )

    def test_notification_str_representation(self):
        """Test the string representation of a notification"""
        self.assertEqual(
            str(self.notification), "1234567890 - appointment_confirmation - pending"
        )

    def test_notification_status_transition(self):
        """Test notification status transitions"""
        # Initial status should be 'pending'
        self.assertEqual(self.notification.status, "pending")

        # Update to 'sent'
        self.notification.status = "sent"
        self.notification.sent_at = timezone.now()
        self.notification.save()

        # Refresh from DB
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "sent")
        self.assertIsNotNone(self.notification.sent_at)

        # Update to 'delivered'
        self.notification.status = "delivered"
        self.notification.delivered_at = timezone.now()
        self.notification.save()

        # Refresh from DB
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "delivered")
        self.assertIsNotNone(self.notification.delivered_at)

        # Update to 'read'
        self.notification.status = "read"
        self.notification.read_at = timezone.now()
        self.notification.save()

        # Refresh from DB
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "read")
        self.assertIsNotNone(self.notification.read_at)


class DeviceTokenTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="1234567890", email="test@example.com"
        )

        # Create a device token
        self.device_token = DeviceToken.objects.create(
            user=self.user,
            token="sample-token-123456789",
            platform="ios",
            device_id="iPhone12-ABCDEF",
        )

    def test_device_token_str_representation(self):
        """Test the string representation of a device token"""
        self.assertEqual(str(self.device_token), "1234567890 - iOS")

    def test_device_token_is_active_by_default(self):
        """Test that device tokens are active by default"""
        self.assertTrue(self.device_token.is_active)
