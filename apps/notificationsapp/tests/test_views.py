from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification


class NotificationViewSetTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(phone_number="1234567890", email="test@example.com")

        # Create another user (for isolation testing)
        self.other_user = User.objects.create(phone_number="9876543210", email="other@example.com")

        # Create notifications for the user
        for i in range(5):
            Notification.objects.create(
                user=self.user,
                type="test_notification",
                channel="in_app",
                subject=f"Test Notification {i}",
                body=f"Test body {i}",
                status="sent",
            )

        # Create read notification
        self.read_notification = Notification.objects.create(
            user=self.user,
            type="test_notification",
            channel="in_app",
            subject="Read Notification",
            body="This notification is read",
            status="read",
            read_at=timezone.now(),
        )

        # Create notifications for the other user
        for i in range(3):
            Notification.objects.create(
                user=self.other_user,
                type="test_notification",
                channel="in_app",
                subject=f"Other User Notification {i}",
                body=f"Other user test body {i}",
                status="sent",
            )

        # Set up API client
        self.client = APIClient()

        # Get auth token for user
        from apps.authapp.services.token_service import TokenService

        tokens = TokenService.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    def test_list_user_notifications(self):
        """Test listing user's notifications"""
        url = reverse("notification-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should have 6 notifications (5 sent + 1 read)
        self.assertEqual(len(response.data["results"]), 6)

        # All notifications should belong to the authenticated user
        for notification in response.data["results"]:
            # Get the notification and check the user
            notif = Notification.objects.get(id=notification["id"])
            self.assertEqual(notif.user, self.user)

    def test_get_unread_notifications(self):
        """Test getting only unread notifications"""
        url = reverse("notification-unread")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should have 5 unread (sent) notifications
        self.assertEqual(len(response.data["results"]), 5)

        # All should have status 'sent'
        for notification in response.data["results"]:
            notif = Notification.objects.get(id=notification["id"])
            self.assertEqual(notif.status, "sent")

    def test_mark_notification_read(self):
        """Test marking a notification as read"""
        # Get first sent notification
        notification = Notification.objects.filter(user=self.user, status="sent").first()

        url = reverse("notification-mark-read", args=[notification.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh notification from DB
        notification.refresh_from_db()

        # Status should be updated to 'read'
        self.assertEqual(notification.status, "read")
        self.assertIsNotNone(notification.read_at)

    def test_mark_all_read(self):
        """Test marking all notifications as read"""
        url = reverse("notification-mark-all-read")
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # All the user's notifications should now be read
        unread_count = Notification.objects.filter(
            user=self.user, status__in=["sent", "delivered"]
        ).count()

        self.assertEqual(unread_count, 0)

    def test_count_unread(self):
        """Test getting unread count"""
        url = reverse("notification-count-unread")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 5)


class DeviceTokenViewSetTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(phone_number="1234567890", email="test@example.com")

        # Create a device token
        self.device_token = DeviceToken.objects.create(
            user=self.user,
            token="existing-token-123456789",
            platform="ios",
            device_id="iPhone12-ABCDEF",
        )

        # Set up API client
        self.client = APIClient()

        # Get auth token for user
        from apps.authapp.services.token_service import TokenService

        tokens = TokenService.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    def test_create_device_token(self):
        """Test creating a new device token"""
        url = reverse("device-token-list")
        data = {
            "token": "new-token-987654321",
            "platform": "android",
            "device_id": "Pixel6-XYZABC",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Token should be created and associated with the user
        token_exists = DeviceToken.objects.filter(
            user=self.user,
            token=data["token"],
            platform=data["platform"],
            device_id=data["device_id"],
        ).exists()

        self.assertTrue(token_exists)

    def test_list_device_tokens(self):
        """Test listing user's device tokens"""
        url = reverse("device-token-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should have 1 token
        self.assertEqual(len(response.data), 1)

        # Token details should match
        self.assertEqual(response.data[0]["token"], self.device_token.token)
        self.assertEqual(response.data[0]["platform"], self.device_token.platform)
        self.assertEqual(response.data[0]["device_id"], self.device_token.device_id)

    def test_delete_device_token(self):
        """Test deleting a device token"""
        url = reverse("device-token-detail", args=[self.device_token.id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Token should be deleted
        token_exists = DeviceToken.objects.filter(id=self.device_token.id).exists()
        self.assertFalse(token_exists)

    def test_delete_by_device_id(self):
        """Test deleting device tokens by device ID"""
        url = reverse("device-token-delete-by-device-id")
        url += f"?device_id={self.device_token.device_id}"

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Token should be deleted
        token_exists = DeviceToken.objects.filter(device_id=self.device_token.device_id).exists()
        self.assertFalse(token_exists)
