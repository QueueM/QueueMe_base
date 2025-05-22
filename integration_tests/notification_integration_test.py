#!/usr/bin/env python
"""
Integration Test for Notification System with Firebase

This test verifies that:
1. Notifications can be sent through different channels (push, SMS, email)
2. Firebase push notifications are delivered
3. Retry mechanism works for failed notifications
4. Rate limiting works correctly
"""

import os
import sys
import unittest
import uuid
from unittest.mock import patch

# Add project to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")

import django

django.setup()

from django.core.cache import cache
from django.test import override_settings

from apps.authapp.models import User
from apps.notificationsapp.models import (
    DeadLetterNotification,
    DeviceToken,
    Notification,
)
from apps.notificationsapp.services.notification_service import NotificationService
from apps.notificationsapp.services.push_service import FirebasePushService

# Test constants
TEST_MODE = True  # Set to True to use mocks, False to test against real services
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"  # Example UUID


class MockFirebaseMessaging:
    """Mock for Firebase messaging module"""

    @staticmethod
    def Message(notification, data, token):
        """Mock Message constructor"""
        return {"notification": notification, "data": data, "token": token}

    @staticmethod
    def MulticastMessage(notification, data, tokens):
        """Mock MulticastMessage constructor"""
        return {"notification": notification, "data": data, "tokens": tokens}

    @staticmethod
    def Notification(title, body):
        """Mock Notification constructor"""
        return {"title": title, "body": body}

    @staticmethod
    def send(message):
        """Mock send method"""
        return f"message_id_{uuid.uuid4()}"

    @staticmethod
    def send_multicast(message):
        """Mock send_multicast method"""

        class Response:
            def __init__(self):
                self.success_count = len(message.get("tokens", []))
                self.failure_count = 0

        return Response()


class NotificationIntegrationTest(unittest.TestCase):
    """Integration tests for the notification system"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.user, created = User.objects.get_or_create(
            id=TEST_USER_ID,
            defaults={
                "phone_number": "+966555555555",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Create test device token
        DeviceToken.objects.get_or_create(
            user=cls.user,
            token="test_device_token_123",
            device_id="test_device_123",
            platform="android",
            is_active=True,
        )

        if TEST_MODE:
            # Mock Firebase SDK
            cls.firebase_messaging_patcher = patch(
                "apps.notificationsapp.services.push_service.messaging",
                MockFirebaseMessaging,
            )
            cls.firebase_messaging_mock = cls.firebase_messaging_patcher.start()

            # Mock SMS service
            cls.sms_service_patcher = patch(
                "apps.notificationsapp.tasks.SMSService.send_sms"
            )
            cls.sms_service_mock = cls.sms_service_patcher.start()
            cls.sms_service_mock.return_value = {
                "success": True,
                "message_id": "test_sms_123",
            }

            # Mock email service
            cls.email_service_patcher = patch("django.core.mail.send_mail")
            cls.email_service_mock = cls.email_service_patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        if TEST_MODE:
            cls.firebase_messaging_patcher.stop()
            cls.sms_service_patcher.stop()
            cls.email_service_patcher.stop()

        # Clean up test data
        DeviceToken.objects.filter(user=cls.user).delete()

    def setUp(self):
        """Set up each test"""
        # Clear cache rate limit keys
        cache.clear()

        # Clear notifications created by tests
        Notification.objects.filter(title__startswith="Test Notification").delete()
        DeadLetterNotification.objects.filter(
            title__startswith="Test Notification"
        ).delete()

    def test_send_notification_all_channels(self):
        """Test sending a notification through all channels"""
        result = NotificationService.send_notification(
            recipient_id=str(self.user.id),
            notification_type="test",
            title="Test Notification All Channels",
            message="This is a test notification sent to all channels",
            channels=["push", "sms", "email", "in_app"],
            data={"test_key": "test_value"},
            priority="high",
        )

        # Check result
        self.assertTrue(result["success"], "Notification sending should succeed")
        self.assertIsNotNone(
            result["notification_id"], "Notification ID should be returned"
        )

        # Verify notification in database
        notification = Notification.objects.get(id=result["notification_id"])
        self.assertEqual(
            notification.title, "Test Notification All Channels", "Title should match"
        )
        self.assertEqual(
            notification.recipient_id, self.user.id, "Recipient should match"
        )
        self.assertEqual(
            notification.status, "processing", "Status should be processing"
        )
        self.assertIn("in_app", notification.channels, "in_app should be in channels")

        # Check in_app channel status (should be immediate)
        self.assertEqual(
            notification.channel_status.get("in_app", {}).get("status"),
            "delivered",
            "in_app channel status should be delivered immediately",
        )

        # Other channels are processed asynchronously in real usage
        # In a real environment, we'd need to wait for tasks to complete

    def test_firebase_push_integration(self):
        """Test direct integration with Firebase Push service"""
        if TEST_MODE:
            # Direct test of Firebase push integration
            result = FirebasePushService.send_to_device(
                token="test_device_token_123",
                title="Test Direct Firebase Push",
                body="Testing direct push notification",
                data={"source": "integration_test"},
            )

            self.assertTrue(result["success"], "Direct push should succeed")
            self.assertIn("message_id", result, "Message ID should be returned")

            # Test sending to multiple devices
            multi_result = FirebasePushService.send_to_multiple_devices(
                tokens=["token1", "token2", "token3"],
                title="Test Multi-device Push",
                body="Testing push to multiple devices",
                data={"source": "integration_test"},
            )

            self.assertTrue(multi_result["success"], "Multi-device push should succeed")
            self.assertEqual(
                multi_result["success_count"], 3, "All devices should succeed"
            )

    def test_idempotency_key(self):
        """Test idempotency key functionality"""
        # Generate unique idempotency key
        idempotency_key = str(uuid.uuid4())

        # Send first notification
        result1 = NotificationService.send_notification(
            recipient_id=str(self.user.id),
            notification_type="test",
            title="Test Notification Idempotency",
            message="This is a test of idempotency",
            channels=["in_app"],
            idempotency_key=idempotency_key,
        )

        # Send duplicate notification with same key
        result2 = NotificationService.send_notification(
            recipient_id=str(self.user.id),
            notification_type="test",
            title="Test Notification Idempotency (Different Title)",  # Different title
            message="This is a duplicate notification",  # Different message
            channels=["in_app"],
            idempotency_key=idempotency_key,
        )

        # IDs should be identical
        self.assertEqual(
            result1["notification_id"],
            result2["notification_id"],
            "Same notification ID should be returned for same idempotency key",
        )

        # Count notifications - there should only be one
        count = Notification.objects.filter(
            title="Test Notification Idempotency"
        ).count()

        self.assertEqual(
            count, 1, "Only one notification should exist despite multiple API calls"
        )

    def test_rate_limiting(self):
        """Test notification rate limiting"""
        # Override rate limits for testing
        with override_settings(
            SMS_RATE_LIMIT={"user": 2, "global": 10},  # Lower limits for testing
            EMAIL_RATE_LIMIT={"user": 3, "global": 15},
        ):
            # Send SMS notifications up to limit
            for i in range(3):  # One more than the limit
                result = NotificationService.send_notification(
                    recipient_id=str(self.user.id),
                    notification_type="test",
                    title=f"Test SMS Rate Limit {i}",
                    message="Testing SMS rate limiting",
                    channels=["sms"],
                )

                # First two should succeed with SMS, third should fail SMS but succeed overall
                if i < 2:
                    self.assertIn(
                        "sms",
                        result["channels_status"],
                        "SMS should be in channels status",
                    )
                else:
                    self.assertNotIn(
                        "sms", result["channels_status"], "SMS should be rate limited"
                    )

            # Send email notifications up to limit
            for i in range(4):  # One more than the limit
                result = NotificationService.send_notification(
                    recipient_id=str(self.user.id),
                    notification_type="test",
                    title=f"Test Email Rate Limit {i}",
                    message="Testing email rate limiting",
                    channels=["email"],
                )

                # First three should succeed with email, fourth should fail email but succeed overall
                if i < 3:
                    self.assertIn(
                        "email",
                        result["channels_status"],
                        "Email should be in channels status",
                    )
                else:
                    self.assertNotIn(
                        "email",
                        result["channels_status"],
                        "Email should be rate limited",
                    )

    def test_retry_mechanism(self):
        """Test notification retry mechanism"""
        with patch(
            "apps.notificationsapp.services.notification_service.NotificationService.retry_notification"
        ) as retry_mock:
            # Create a notification that will fail
            notification = Notification.objects.create(
                recipient_id=self.user.id,
                notification_type="test",
                title="Test Notification Retry",
                message="This notification will fail and retry",
                channels=["push", "sms"],
                status="processing",
                retry_count={"push": 0, "sms": 0},
            )

            # Simulate failure and update
            NotificationService.update_notification_status(
                notification_id=str(notification.id),
                channel="push",
                status="error",
                error_message="Test error for retry",
            )

            # Retry should be scheduled
            retry_mock.assert_called_once_with(str(notification.id), "push")

            # Check retry count was incremented
            notification.refresh_from_db()
            self.assertEqual(
                notification.retry_count.get("push"),
                1,
                "Retry count should be incremented",
            )

    def test_dead_letter_queue(self):
        """Test dead letter queue for failed notifications"""
        # Create a notification that will fail maximum times
        notification = Notification.objects.create(
            recipient_id=self.user.id,
            notification_type="test",
            title="Test Notification DLQ",
            message="This notification will go to dead letter queue",
            channels=["push", "sms", "email"],
            status="processing",
            retry_count={
                "push": 5,
                "sms": 0,
                "email": 0,
            },  # push already at max retries
        )

        # Update status to error (which should move to DLQ since retry count is at max)
        NotificationService.update_notification_status(
            notification_id=str(notification.id),
            channel="push",
            status="error",
            error_message="Test error for dead letter queue",
        )

        # Check if notification went to dead letter queue
        dlq_notification = DeadLetterNotification.objects.filter(
            original_notification_id=notification.id, channel="push"
        ).first()

        self.assertIsNotNone(
            dlq_notification, "Notification should be in dead letter queue"
        )
        self.assertEqual(
            dlq_notification.error_message,
            "Test error for dead letter queue",
            "Error message should match",
        )
        self.assertEqual(dlq_notification.retry_count, 5, "Retry count should match")


if __name__ == "__main__":
    unittest.main()
