from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate
from apps.notificationsapp.services.channel_selector import ChannelSelector
from apps.notificationsapp.services.notification_service import NotificationService
from apps.notificationsapp.services.timing_optimizer import TimingOptimizer


class NotificationServiceTest(TestCase):
    def setUp(self):
        # Create test data
        self.user = User.objects.create(phone_number="1234567890", email="test@example.com")

        # Create notification templates
        self.sms_template = NotificationTemplate.objects.create(
            type="test_notification",
            channel="sms",
            subject="Test Notification",
            body_en="This is a test notification with {{variable}}.",
            body_ar="هذا إشعار اختبار مع {{variable}}.",
            variables=["variable"],
        )

        self.email_template = NotificationTemplate.objects.create(
            type="test_notification",
            channel="email",
            subject="Test Email Notification",
            body_en="This is a test email with {{variable}}.",
            body_ar="هذا بريد إلكتروني للاختبار مع {{variable}}.",
            variables=["variable"],
        )

        self.push_template = NotificationTemplate.objects.create(
            type="test_notification",
            channel="push",
            subject="Test Push Notification",
            body_en="This is a test push notification with {{variable}}.",
            body_ar="هذا إشعار دفع للاختبار مع {{variable}}.",
            variables=["variable"],
        )

        self.in_app_template = NotificationTemplate.objects.create(
            type="test_notification",
            channel="in_app",
            subject="Test In-App Notification",
            body_en="This is a test in-app notification with {{variable}}.",
            body_ar="هذا إشعار داخل التطبيق للاختبار مع {{variable}}.",
            variables=["variable"],
        )

        # Create device token for push
        self.device_token = DeviceToken.objects.create(
            user=self.user,
            token="sample-token-123456789",
            platform="ios",
            device_id="iPhone12-ABCDEF",
        )

    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_sms")
    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_email")
    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_push")
    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_in_app")
    def test_send_notification_all_channels(self, mock_in_app, mock_push, mock_email, mock_sms):
        """Test sending notification through all channels"""
        # Set up mocks to return True (success)
        mock_sms.return_value = True
        mock_email.return_value = True
        mock_push.return_value = True
        mock_in_app.return_value = True

        # Send notification
        notifications = NotificationService.send_notification(
            user_id=self.user.id,
            notification_type="test_notification",
            data={"variable": "test value"},
            channels=["sms", "email", "push", "in_app"],
        )

        # Check if notifications were created
        self.assertEqual(len(notifications), 4)

        # Verify that each send method was called
        mock_sms.assert_called_once()
        mock_email.assert_called_once()
        mock_push.assert_called_once()
        mock_in_app.assert_called_once()

        # Check notification statuses
        for notification in notifications:
            self.assertEqual(notification.status, "sent")
            self.assertIsNotNone(notification.sent_at)

    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_sms")
    def test_notification_template_rendering(self, mock_sms):
        """Test that templates are correctly rendered with data"""
        mock_sms.return_value = True

        data = {"variable": "test value"}

        notifications = NotificationService.send_notification(
            user_id=self.user.id,
            notification_type="test_notification",
            data=data,
            channels=["sms"],
        )

        self.assertEqual(len(notifications), 1)
        notification = notifications[0]

        # Check that template was rendered with data
        self.assertEqual(notification.body, "This is a test notification with test value.")

    @patch("apps.notificationsapp.services.notification_service.NotificationService._send_sms")
    def test_scheduled_notification(self, mock_sms):
        """Test scheduling a notification for future delivery"""
        # Don't call the send method yet
        mock_sms.return_value = True

        # Schedule for 1 hour in the future
        scheduled_time = timezone.now() + timezone.timedelta(hours=1)

        notifications = NotificationService.send_notification(
            user_id=self.user.id,
            notification_type="test_notification",
            data={"variable": "test value"},
            scheduled_for=scheduled_time,
            channels=["sms"],
        )

        self.assertEqual(len(notifications), 1)
        notification = notifications[0]

        # Check that it's pending and has scheduled_for set
        self.assertEqual(notification.status, "pending")
        self.assertEqual(notification.scheduled_for, scheduled_time)

        # Ensure send method wasn't called yet
        mock_sms.assert_not_called()


class ChannelSelectorTest(TestCase):
    def setUp(self):
        # Create test data
        self.user = User.objects.create(phone_number="1234567890", email="test@example.com")

        # Create device token for push
        self.device_token = DeviceToken.objects.create(
            user=self.user,
            token="sample-token-123456789",
            platform="ios",
            device_id="iPhone12-ABCDEF",
        )

    def test_select_optimal_channels_critical(self):
        """Test channel selection for critical notification types"""
        # Test critical notification (should prefer immediate channels)
        channels = ChannelSelector.select_optimal_channels(
            user_id=self.user.id,
            notification_type="verification_code",  # Critical urgency
        )

        # Should include push (immediate) since user has device token
        self.assertIn("push", channels)

        # For critical, might also include SMS if available
        if "sms" in channels:
            self.assertEqual(set(channels), set(["push", "sms"]))
        else:
            self.assertEqual(channels, ["push"])

    def test_select_optimal_channels_low_urgency(self):
        """Test channel selection for low urgency notification types"""
        # Test low urgency notification (can use less immediate channels)
        channels = ChannelSelector.select_optimal_channels(
            user_id=self.user.id, notification_type="service_feedback"  # Low urgency
        )

        # Should choose just one channel for low urgency
        self.assertEqual(len(channels), 1)

        # Should be one of the available channels (push, email, in-app)
        self.assertIn(channels[0], ["push", "email", "in_app"])

    def test_channel_availability_check(self):
        """Test that channel selection respects channel availability"""
        # Create user without email
        user_no_email = User.objects.create(phone_number="0987654321", email=None)  # No email

        # No device token either

        channels = ChannelSelector.select_optimal_channels(
            user_id=user_no_email.id, notification_type="appointment_confirmation"
        )

        # Should not include email or push, but include SMS and maybe in-app
        self.assertNotIn("email", channels)
        self.assertNotIn("push", channels)
        self.assertTrue(set(channels).issubset(set(["sms", "in_app"])))


class TimingOptimizerTest(TestCase):
    def setUp(self):
        # Create test data
        self.user = User.objects.create(phone_number="1234567890", email="test@example.com")

        # Create some read notifications to establish pattern
        template = NotificationTemplate.objects.create(
            type="test_notification",
            channel="in_app",
            subject="Test Notification",
            body_en="Test body",
            body_ar="Test body in Arabic",
        )

        # Create notifications read at specific times to establish a pattern
        # User usually reads at 8 AM and 8 PM
        morning = timezone.now().replace(hour=8, minute=0)
        evening = timezone.now().replace(hour=20, minute=0)

        for i in range(5):
            unused_notification = Notification.objects.create(
                user=self.user,
                template=template,
                type="test_notification",
                channel="in_app",
                subject="Morning Notification",
                body="Morning test",
                status="read",
                read_at=morning - timezone.timedelta(days=i),
            )

            # Create evening notification
            unused_evening_notification = Notification.objects.create(
                user=self.user,
                template=template,
                type="test_notification",
                channel="in_app",
                subject="Evening Notification",
                body="Evening test",
                status="read",
                read_at=evening - timezone.timedelta(days=i),
            )

    def test_immediate_notification_no_delay(self):
        """Test that urgent notifications get no delay"""
        result = TimingOptimizer.determine_optimal_send_time(
            user_id=self.user.id, notification_type="verification_code"  # Immediate
        )

        # Should return None for immediate sending
        self.assertIsNone(result)

    def test_optimize_timing_for_feedback(self):
        """Test timing optimization for non-urgent notification"""
        # We'll use current time for reference
        now = timezone.now()

        result = TimingOptimizer.determine_optimal_send_time(
            user_id=self.user.id,
            notification_type="service_feedback",  # Non-urgent, can be delayed
        )

        # If result is None, it means send immediately (acceptable)
        if result is not None:
            # Otherwise, should be in the future
            self.assertGreater(result, now)

            # Should be within the max delay for this notification type
            max_delay = TimingOptimizer.MAX_DELAY.get("service_feedback", 0)
            max_future = now + timezone.timedelta(hours=max_delay)

            self.assertLessEqual(result, max_future)

            # Should be at a time when user is likely to be active
            user_hour = result.hour

            # Our test user is active at 8 AM and 8 PM
            # It should schedule near one of these times
            self.assertTrue(
                (7 <= user_hour <= 9) or (19 <= user_hour <= 21),  # Morning  # Evening
                f"Scheduled for {user_hour} which is not an active time for this user",
            )
