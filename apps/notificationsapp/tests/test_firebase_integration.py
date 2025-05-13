"""
Tests for Firebase SMS and push notification integration.
"""

import json
import uuid
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notificationsapp.models import (
    DeviceToken,
    Notification,
    NotificationTemplate,
    NotificationType,
)
from apps.notificationsapp.services.notification_service import NotificationService
from apps.notificationsapp.services.push_service import FirebasePushService
from apps.notificationsapp.services.sms_service import SMSProvider, SMSService

User = get_user_model()


class MockFirebaseResponse:
    """
    Mock response for Firebase API calls
    """

    def __init__(self, success=True, failure=0, canonical_ids=0, results=None):
        self.success = success
        self.data = {
            "success": success,
            "failure": failure,
            "canonical_ids": canonical_ids,
            "results": results or [{"message_id": "test_message_id"}],
        }

    def json(self):
        return self.data

    def raise_for_status(self):
        if not self.success:
            raise Exception("Firebase API Error")


class FirebaseIntegrationTest(TestCase):
    """Test Firebase integration for SMS and push notifications"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            phone_number="+966500000000",
        )

        # Create test device token
        self.device_token = DeviceToken.objects.create(
            user=self.user, token="test_device_token", device_type="android"
        )

        # Create notification type
        self.notification_type = NotificationType.objects.create(
            name="test_notification",
            title_template="Test Notification",
            body_template="This is a test notification for {user}",
            priority="normal",
        )

        # Store original settings
        self.original_firebase_settings = getattr(settings, "FIREBASE_CONFIG", {})
        self.original_sms_provider = getattr(settings, "SMS_PROVIDER", None)

        # Configure Firebase settings for testing
        settings.FIREBASE_CONFIG = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "PLACEHOLDER_PRIVATE_KEY",  # Using placeholder instead of actual key
            "client_email": "firebase-adminsdk@test-project.iam.gserviceaccount.com",
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk%40test-project.iam.gserviceaccount.com",
            "fcm_api_key": "test-fcm-api-key",
            "server_key": "test-server-key",
        }

        # Set SMS provider to Firebase
        settings.SMS_PROVIDER = SMSProvider.FIREBASE

    def tearDown(self):
        # Restore original settings
        settings.FIREBASE_CONFIG = self.original_firebase_settings
        settings.SMS_PROVIDER = self.original_sms_provider

    @mock.patch("firebase_admin.messaging.send_multicast")
    def test_send_push_notification(self, mock_send_multicast):
        """Test sending push notifications through Firebase"""
        # Mock the Firebase response
        mock_send_multicast.return_value = mock.MagicMock(
            success_count=1,
            failure_count=0,
            responses=[mock.MagicMock(success=True, message_id="test_message_id")],
        )

        # Send a push notification
        result = FirebasePushService.send_notification(
            user_ids=[str(self.user.id)],
            title="Test Push",
            body="This is a test push notification",
            data={"test_key": "test_value"},
            priority="high",
        )

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["sent_count"], 1)

        # Verify Firebase API was called with correct parameters
        mock_send_multicast.assert_called_once()
        args = mock_send_multicast.call_args[0][0]

        # Check notification content
        self.assertEqual(args.notification.title, "Test Push")
        self.assertEqual(args.notification.body, "This is a test push notification")

        # Check that token was included
        self.assertEqual(args.tokens, ["test_device_token"])

        # Check that data was included
        self.assertEqual(args.data, {"test_key": "test_value"})

    @mock.patch("requests.post")
    def test_send_sms_via_firebase(self, mock_post):
        """Test sending SMS via Firebase"""
        # Mock the Firebase SMS API response
        mock_post.return_value = MockFirebaseResponse(success=True)

        # Send an SMS
        result = SMSService.send_sms(
            phone_number="+966500000000",
            message="This is a test SMS message",
            sender_id="QueueMe",
        )

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "firebase")

        # Verify Firebase API was called with correct parameters
        mock_post.assert_called_once()
        args = mock_post.call_args

        # Verify the Firebase URL was used
        self.assertTrue("firebasesms" in args[0][0])

        # Verify the message content was sent
        payload = json.loads(args[1]["data"])
        self.assertEqual(payload["message"], "This is a test SMS message")
        self.assertEqual(payload["phone"], "+966500000000")

    @mock.patch("firebase_admin.messaging.send_multicast")
    def test_notification_delivery_tracking(self, mock_send_multicast):
        """Test that notifications are properly tracked in the database"""
        # Mock the Firebase response
        mock_send_multicast.return_value = mock.MagicMock(
            success_count=1,
            failure_count=0,
            responses=[mock.MagicMock(success=True, message_id="test_message_id")],
        )

        # Send a notification
        FirebasePushService.send_notification(
            user_ids=[str(self.user.id)],
            title="Test Tracking",
            body="This is a test notification for tracking",
            data={"notification_type": "test_type"},
            priority="normal",
        )

        # Verify notification was created in database
        notification = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title, "Test Tracking")
        self.assertEqual(notification.message, "This is a test notification for tracking")
        self.assertEqual(notification.status, "sent")

        # Verify delivery details were recorded
        self.assertEqual(notification.provider, "firebase")
        self.assertTrue(notification.provider_response is not None)

    @mock.patch("firebase_admin.messaging.send_multicast")
    def test_handle_failed_notification(self, mock_send_multicast):
        """Test handling of failed notifications"""
        # Mock a failed Firebase response
        mock_send_multicast.return_value = mock.MagicMock(
            success_count=0,
            failure_count=1,
            responses=[mock.MagicMock(success=False, exception=Exception("Invalid token"))],
        )

        # Send a notification that will fail
        result = FirebasePushService.send_notification(
            user_ids=[str(self.user.id)],
            title="Failed Test",
            body="This notification should fail",
            data={},
            priority="normal",
        )

        # Verify result indicates failure
        self.assertFalse(result.get("success", True))
        self.assertEqual(result.get("failed_count", 0), 1)

        # Verify notification was still created but marked as failed
        notification = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.status, "failed")

        # Check that error info was recorded
        self.assertTrue("error" in notification.provider_response)


class NotificationServiceIntegrationTests(TestCase):
    """
    Tests for the NotificationService with Firebase integrations
    """

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="test_integration",
            email="integration@example.com",
            password="testpassword123",
            phone_number="+966500000000",
        )

        # Create device token
        self.device_token = DeviceToken.objects.create(
            user=self.user,
            token="integration_fcm_token",
            device_type="ios",
            is_active=True,
        )

        # Create notification templates
        self.sms_template = NotificationTemplate.objects.create(
            name="integration_sms",
            title="SMS Integration",
            body="Hello {name}, this is an SMS integration test.",
            type="sms",
        )

        self.push_template = NotificationTemplate.objects.create(
            name="integration_push",
            title="Push Integration",
            body="Hello {name}, this is a push integration test.",
            type="push",
        )

    @mock.patch("apps.notificationsapp.services.sms_service.SMSService.send_sms")
    def test_send_sms_notification_through_service(self, mock_send_sms):
        """Test sending SMS through the NotificationService"""
        # Mock the SMS service
        mock_send_sms.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "test_sms_id_789",
        }

        # Send notification through service
        notification = NotificationService.send_notification(
            user_id=self.user.id,
            template_name="integration_sms",
            context={"name": "Integration User"},
        )

        # Verify SMS service was called correctly
        mock_send_sms.assert_called_once()
        args, kwargs = mock_send_sms.call_args

        # Verify SMS content
        self.assertEqual(args[0], self.user.phone_number)
        self.assertEqual(args[1], "Hello Integration User, this is an SMS integration test.")

        # Verify notification was created and updated
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.provider, "firebase")
        self.assertEqual(notification.external_id, "test_sms_id_789")

    @mock.patch(
        "apps.notificationsapp.services.push_service.FirebasePushService.send_push_notification"
    )
    def test_send_push_notification_through_service(self, mock_send_push):
        """Test sending push notification through the NotificationService"""
        # Mock the push service
        mock_send_push.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "test_push_id_789",
        }

        # Send notification through service
        notification = NotificationService.send_notification(
            user_id=self.user.id,
            template_name="integration_push",
            context={"name": "Integration User"},
            data={"action": "test_action"},
        )

        # Verify push service was called correctly
        mock_send_push.assert_called_once()
        args, kwargs = mock_send_push.call_args

        # Verify push content
        self.assertEqual(args[0], self.user.id)
        self.assertEqual(args[1], "Push Integration")
        self.assertEqual(args[2], "Hello Integration User, this is a push integration test.")
        self.assertEqual(kwargs["data"]["action"], "test_action")

        # Verify notification was created and updated
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.provider, "firebase")
        self.assertEqual(notification.external_id, "test_push_id_789")

    @mock.patch("apps.notificationsapp.services.sms_service.SMSService.send_sms")
    @mock.patch(
        "apps.notificationsapp.services.push_service.FirebasePushService.send_push_notification"
    )
    def test_notification_preference_respected(self, mock_send_push, mock_send_sms):
        """Test that user notification preferences are respected"""
        # Set up user preferences to only receive push
        self.user.notification_preferences = {
            "sms_enabled": False,
            "push_enabled": True,
            "email_enabled": True,
        }
        self.user.save()

        # Prepare mock responses
        mock_send_push.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "test_pref_push_id",
        }

        mock_send_sms.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "test_pref_sms_id",
        }

        # Send SMS notification (should be blocked by preferences)
        notification = NotificationService.send_notification(
            user_id=self.user.id,
            template_name="integration_sms",
            context={"name": "Preference User"},
        )

        # Verify SMS was not sent
        mock_send_sms.assert_not_called()

        # Verify notification was created but marked as skipped
        self.assertEqual(notification.status, "skipped")
        self.assertEqual(notification.skip_reason, "user_preference")

        # Send push notification (should be allowed by preferences)
        notification = NotificationService.send_notification(
            user_id=self.user.id,
            template_name="integration_push",
            context={"name": "Preference User"},
        )

        # Verify push was sent
        mock_send_push.assert_called_once()

        # Verify notification was created and updated
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.provider, "firebase")
