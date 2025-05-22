import unittest
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from apps.notificationsapp.services.sms_service import SMSProvider, SMSService


class SMSServiceTestCase(SimpleTestCase):
    """Test cases for the SMS service."""

    def setUp(self):
        """Set up the test environment."""
        # Store original settings to restore them later
        self.original_sms_provider = getattr(
            settings, "SMS_PROVIDER", SMSProvider.TWILIO
        )

    def tearDown(self):
        """Clean up after tests."""
        # Restore original settings
        settings.SMS_PROVIDER = self.original_sms_provider

    @patch("apps.notificationsapp.services.sms_service.SMSService._send_via_twilio")
    def test_send_sms_with_twilio(self, mock_send_via_twilio):
        """Test sending SMS via Twilio provider."""
        # Configure mock
        mock_send_via_twilio.return_value = {
            "success": True,
            "provider": "twilio",
            "message_id": "mock-message-id",
            "status": "sent",
        }

        # Force provider to Twilio
        settings.SMS_PROVIDER = SMSProvider.TWILIO

        # Call the method under test
        result = SMSService.send_sms(
            phone_number="+123456789",
            message="Test message",
        )

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "twilio")
        self.assertEqual(result["status"], "sent")

        # Verify the mock was called with correct arguments
        mock_send_via_twilio.assert_called_once_with("+123456789", "Test message", None)

    @patch("apps.notificationsapp.services.sms_service.SMSService._send_via_firebase")
    def test_send_sms_with_firebase(self, mock_send_via_firebase):
        """Test sending SMS via Firebase provider."""
        # Configure mock
        mock_send_via_firebase.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "mock-message-id",
            "status": "sent",
        }

        # Force provider to Firebase
        settings.SMS_PROVIDER = SMSProvider.FIREBASE

        # Call the method under test
        result = SMSService.send_sms(
            phone_number="+123456789",
            message="Test message",
        )

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "firebase")
        self.assertEqual(result["status"], "sent")

        # Verify the mock was called with correct arguments
        mock_send_via_firebase.assert_called_once_with(
            "+123456789", "Test message", None
        )

    def test_clean_phone_number(self):
        """Test phone number cleaning and formatting."""
        # Test with various formats
        test_cases = [
            # (input, expected output)
            ("1234567890", "+11234567890"),  # US number without country code
            ("+1234567890", "+1234567890"),  # Already has plus
            ("(123) 456-7890", "+11234567890"),  # With formatting
            (" +1 (123) 456-7890 ", "+11234567890"),  # With spaces and plus
        ]

        for input_phone, expected_output in test_cases:
            result = SMSService._clean_phone_number(input_phone)
            self.assertEqual(result, expected_output)

    @patch("apps.notificationsapp.services.sms_service.render_to_string")
    @patch("apps.notificationsapp.services.sms_service.SMSService.send_sms")
    def test_send_with_template(self, mock_send_sms, mock_render_to_string):
        """Test sending SMS with a template."""
        # Configure mocks
        mock_render_to_string.return_value = "Rendered template"
        mock_send_sms.return_value = {"success": True}

        # Call the method under test
        result = SMSService.send_with_template(
            phone_number="+123456789",
            template_name="test_template",
            context={"key": "value"},
        )

        # Verify the template was rendered
        mock_render_to_string.assert_called_once_with(
            "notificationsapp/sms/test_template.txt", {"key": "value"}
        )

        # Verify SMS was sent with rendered template
        mock_send_sms.assert_called_once_with("+123456789", "Rendered template")

        # Verify the result
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
