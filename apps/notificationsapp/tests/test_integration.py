import unittest
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase

from apps.notificationsapp.services.notification_service import NotificationService
from apps.notificationsapp.services.sms_service import SMSProvider, SMSService


class NotificationIntegrationTestCase(SimpleTestCase):
    """Test the integration between notification services."""

    def setUp(self):
        """Set up test environment."""
        # Store original SMS provider
        self.original_sms_provider = getattr(settings, "SMS_PROVIDER", SMSProvider.TWILIO)

        # Mock user data
        self.user_id = "test-user-id"
        self.phone_number = "+1234567890"

    def tearDown(self):
        """Clean up after tests."""
        # Restore original settings
        settings.SMS_PROVIDER = self.original_sms_provider

    @patch("apps.notificationsapp.services.notification_service.User.objects.get")
    @patch("apps.notificationsapp.services.notification_service.NotificationTemplate.objects.get")
    @patch("apps.notificationsapp.services.notification_service.Notification.objects.create")
    @patch("apps.notificationsapp.services.notification_service.send_sms_notification_task")
    def test_notification_service_sends_sms(
        self,
        mock_send_sms_task,
        mock_create_notification,
        mock_get_template,
        mock_get_user,
    ):
        """Test that NotificationService successfully sends SMS via SMSService."""
        # Configure mocks
        mock_user = MagicMock()
        mock_user.id = self.user_id
        mock_user.phone_number = self.phone_number
        mock_get_user.return_value = mock_user

        mock_template = MagicMock()
        mock_template.subject = "Test Notification"
        mock_template.render_body.return_value = "This is a test notification with test value."
        mock_get_template.return_value = mock_template

        mock_notification = MagicMock()
        mock_notification.id = "test-notif-id"
        mock_notification.channel = "sms"
        mock_notification.status = "pending"
        mock_notification.channels = ["sms"]
        mock_notification.channel_status = {}
        mock_create_notification.return_value = mock_notification

        # Set SMS provider to mock
        settings.SMS_PROVIDER = SMSProvider.MOCK

        # Send notification via notification service
        result = NotificationService.send_notification(
            recipient_id=self.user_id,
            notification_type="test_notification",
            title="Test notification",
            message="This is a test notification with test value.",
            channels=["sms"],
            data={"variable": "test value"},
        )

        # Verify the result is successful
        self.assertTrue(result["success"])

        # Verify the notification task was called
        mock_send_sms_task.delay.assert_called_once()

    @patch("apps.notificationsapp.services.sms_service.SMSService._send_via_mock")
    def test_direct_sms_sending(self, mock_send_via_mock):
        """Test sending SMS directly."""
        # Configure mock
        mock_send_via_mock.return_value = {
            "success": True,
            "provider": "mock",
            "message_id": "mock-message-id",
            "status": "sent",
        }

        # Set SMS provider to mock
        settings.SMS_PROVIDER = SMSProvider.MOCK

        # Send SMS directly
        message = "This is a direct test message"
        result = SMSService.send_sms(phone_number=self.phone_number, message=message)

        # Verify SMS was sent
        self.assertTrue(result["success"])

        # Verify the mock was called with correct arguments
        mock_send_via_mock.assert_called_once()
        args, kwargs = mock_send_via_mock.call_args
        self.assertEqual(
            args[0], "+" + self.phone_number.lstrip("+")
        )  # Should be normalized with +
        self.assertEqual(args[1], message)


if __name__ == "__main__":
    unittest.main()
