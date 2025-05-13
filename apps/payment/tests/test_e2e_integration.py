"""
End-to-end tests for Moyasar payment integration with Firebase notifications.
"""

import json
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate
from apps.notificationsapp.services.notification_service import NotificationService
from apps.notificationsapp.services.push_service import FirebasePushService
from apps.notificationsapp.services.sms_service import SMSService
from apps.payment.models import PaymentWalletType, Transaction
from apps.payment.services.moyasar_service import MoyasarService
from apps.payment.services.payment_service import PaymentService
from apps.payment.views.webhook_views import subscription_webhook
from apps.subscriptionapp.models import Subscription, SubscriptionPlan

User = get_user_model()


class MockMoyasarResponse:
    """Mock Moyasar API response"""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.json_data = json_data or {}

    def json(self):
        return self.json_data


class MockFirebaseResponse:
    """Mock Firebase API response"""

    def __init__(self, success=True, error=None, message_id=None):
        self.success = success
        self.error = error
        self.message_id = message_id or str(uuid.uuid4())

    def json(self):
        if self.success:
            return {"success": True, "message_id": self.message_id}
        else:
            return {"success": False, "error": self.error}


class E2EPaymentNotificationTests(TestCase):
    """
    End-to-end tests for payment flow with notifications
    """

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            username="e2e_test_user",
            email="e2e@example.com",
            password="testpassword123",
            phone_number="+966500000000",
        )

        # Create device token for push notifications
        self.device_token = DeviceToken.objects.create(
            user=self.user, token="e2e_fcm_token", device_type="android", is_active=True
        )

        # Create subscription plan
        self.subscription_plan = SubscriptionPlan.objects.create(
            name="E2E Test Plan",
            price=Decimal("100.00"),
            duration_days=30,
            description="E2E test subscription plan",
        )

        # Create a subscription
        self.subscription = Subscription.objects.create(
            user=self.user, plan=self.subscription_plan, status="pending"
        )

        # Create notification templates
        self.payment_success_push_template = NotificationTemplate.objects.create(
            name="payment_success_push",
            title="Payment Success",
            body="Your payment of {amount} SAR was successful.",
            type="push",
        )

        self.payment_success_sms_template = NotificationTemplate.objects.create(
            name="payment_success_sms",
            title="Payment Success",
            body="Your payment of {amount} SAR for {plan_name} was successful. Thank you!",
            type="sms",
        )

        # Set up API client and request factory
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.factory = RequestFactory()

        # Mock Moyasar settings
        self.moyasar_settings = {
            "subscription": {
                "api_key": "sk_test_subscription",
                "public_key": "pk_test_subscription",
                "wallet_id": "wallet_sub_123",
            }
        }

    @mock.patch("apps.payment.services.moyasar_service.requests.post")
    @mock.patch("apps.payment.services.moyasar_service.MoyasarService.get_wallet_config")
    def test_payment_flow_creation(self, mock_wallet_config, mock_post):
        """Test the initial payment creation flow"""
        # Mock wallet config
        mock_wallet_config.return_value = self.moyasar_settings["subscription"]

        # Mock Moyasar API response for payment creation
        mock_post.return_value = MockMoyasarResponse(
            json_data={
                "id": "payments_e2e_123",
                "status": "initiated",
                "amount": 10000,  # 100 SAR in halalas
                "source": {"type": "creditcard"},
                "url": "https://moyasar.com/payment/e2e_123",
            }
        )

        # Create payment through API
        response = self.client.post(
            reverse("payment-create-payment"),
            data={
                "amount": "100.00",
                "transaction_type": "subscription",
                "content_type": {
                    "app_label": "subscriptionapp",
                    "model": "subscription",
                },
                "object_id": str(self.subscription.id),
                "description": "E2E test payment",
            },
            format="json",
        )

        # Check response
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "initiated")
        self.assertIn("transaction_id", response.data)
        self.assertIn("redirect_url", response.data)

        # Verify transaction was created
        transaction_id = response.data["transaction_id"]
        transaction = Transaction.objects.get(id=transaction_id)
        self.assertEqual(transaction.amount, Decimal("100.00"))
        self.assertEqual(transaction.transaction_type, "subscription")
        self.assertEqual(transaction.status, "initiated")
        self.assertEqual(transaction.moyasar_id, "payments_e2e_123")

        return transaction_id

    @mock.patch(
        "apps.notificationsapp.services.push_service.FirebasePushService.send_push_notification"
    )
    @mock.patch("apps.notificationsapp.services.sms_service.SMSService.send_sms")
    def test_payment_webhook_with_notifications(self, mock_send_sms, mock_send_push):
        """Test payment webhook handling and notifications"""
        # Create a transaction first
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type="subscription",
            status="initiated",
            moyasar_id="payments_e2e_webhook_123",
            content_type=ContentType.objects.get_for_model(Subscription),
            object_id=self.subscription.id,
        )

        # Mock notification responses
        mock_send_push.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "e2e_push_id",
        }

        mock_send_sms.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "e2e_sms_id",
        }

        # Create webhook payload
        webhook_data = {
            "id": "payments_e2e_webhook_123",
            "status": "paid",
            "amount": 10000,  # 100 SAR in halalas
            "source": {"type": "creditcard"},
            "metadata": {
                "transaction_id": str(transaction.id),
                "wallet_type": "subscription",
            },
        }

        # Create request and process webhook
        with mock.patch(
            "apps.payment.services.payment_service.NotificationService.send_notification"
        ) as mock_notify:
            # Mock notification service
            mock_notify.side_effect = [
                Notification(
                    id=uuid.uuid4(),
                    status="sent",
                    provider="firebase",
                    external_id="e2e_push_id",
                ),
                Notification(
                    id=uuid.uuid4(),
                    status="sent",
                    provider="firebase",
                    external_id="e2e_sms_id",
                ),
            ]

            # Process webhook
            request = self.factory.post(
                reverse("subscription_webhook"),
                data=json.dumps(webhook_data),
                content_type="application/json",
            )
            response = subscription_webhook(request)

        # Verify webhook response
        self.assertEqual(response.status_code, 200)

        # Verify transaction was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "succeeded")

        # Verify subscription was updated
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, "active")

        # Verify notifications were sent (or at least attempted)
        self.assertEqual(mock_notify.call_count, 2)  # Both push and SMS

        # Check first call (push notification)
        first_call_args = mock_notify.call_args_list[0][1]
        self.assertEqual(first_call_args["user_id"], self.user.id)
        self.assertEqual(first_call_args["template_name"], "payment_success_push")
        self.assertEqual(first_call_args["context"]["amount"], "100.00")

        # Check second call (SMS)
        second_call_args = mock_notify.call_args_list[1][1]
        self.assertEqual(second_call_args["user_id"], self.user.id)
        self.assertEqual(second_call_args["template_name"], "payment_success_sms")
        self.assertEqual(second_call_args["context"]["amount"], "100.00")
        self.assertEqual(second_call_args["context"]["plan_name"], "E2E Test Plan")

    @mock.patch("apps.payment.services.moyasar_service.requests.post")
    @mock.patch("apps.payment.services.moyasar_service.requests.get")
    @mock.patch("apps.payment.services.moyasar_service.MoyasarService.get_wallet_config")
    @mock.patch(
        "apps.notificationsapp.services.push_service.FirebasePushService.send_push_notification"
    )
    @mock.patch("apps.notificationsapp.services.sms_service.SMSService.send_sms")
    def test_complete_payment_flow(
        self, mock_send_sms, mock_send_push, mock_wallet_config, mock_get, mock_post
    ):
        """Test complete payment flow from creation to notification"""
        # Mock wallet config
        mock_wallet_config.return_value = self.moyasar_settings["subscription"]

        # Mock Moyasar payment creation
        moyasar_payment_id = "payments_complete_123"
        mock_post.return_value = MockMoyasarResponse(
            json_data={
                "id": moyasar_payment_id,
                "status": "initiated",
                "amount": 10000,  # 100 SAR in halalas
                "source": {"type": "creditcard"},
                "url": "https://moyasar.com/payment/complete_123",
            }
        )

        # Mock Moyasar status check
        mock_get.return_value = MockMoyasarResponse(
            json_data={
                "id": moyasar_payment_id,
                "status": "paid",
                "amount": 10000,
                "source": {"type": "creditcard"},
            }
        )

        # Mock push and SMS services
        mock_send_push.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "complete_push_id",
        }

        mock_send_sms.return_value = {
            "success": True,
            "provider": "firebase",
            "message_id": "complete_sms_id",
        }

        # Step 1: Create payment
        response = self.client.post(
            reverse("payment-create-payment"),
            data={
                "amount": "100.00",
                "transaction_type": "subscription",
                "content_type": {
                    "app_label": "subscriptionapp",
                    "model": "subscription",
                },
                "object_id": str(self.subscription.id),
                "description": "Complete flow test payment",
            },
            format="json",
        )

        # Verify payment creation
        self.assertEqual(response.status_code, 201)
        transaction_id = response.data["transaction_id"]

        # Get the transaction
        transaction = Transaction.objects.get(id=transaction_id)
        self.assertEqual(transaction.moyasar_id, moyasar_payment_id)

        # Step 2: Mock user completing payment on Moyasar site
        # (In a real scenario, user would follow redirect_url and complete payment)

        # Step 3: Webhook notification of payment completion
        with mock.patch(
            "apps.payment.services.payment_service.NotificationService.send_notification"
        ) as mock_notify:
            # Mock notification service
            mock_notify.side_effect = [
                Notification(
                    id=uuid.uuid4(),
                    status="sent",
                    provider="firebase",
                    external_id="complete_push_id",
                ),
                Notification(
                    id=uuid.uuid4(),
                    status="sent",
                    provider="firebase",
                    external_id="complete_sms_id",
                ),
            ]

            # Create webhook data
            webhook_data = {
                "id": moyasar_payment_id,
                "status": "paid",
                "amount": 10000,
                "source": {"type": "creditcard"},
                "metadata": {
                    "transaction_id": transaction_id,
                    "wallet_type": "subscription",
                },
            }

            # Process webhook
            request = self.factory.post(
                reverse("subscription_webhook"),
                data=json.dumps(webhook_data),
                content_type="application/json",
            )
            webhook_response = subscription_webhook(request)

        # Verify webhook processed successfully
        self.assertEqual(webhook_response.status_code, 200)

        # Verify transaction status updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "succeeded")

        # Verify subscription status updated
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, "active")

        # Verify notifications were sent
        self.assertEqual(mock_notify.call_count, 2)

        # Step 4: Verify we can check payment status through API
        status_response = self.client.get(
            reverse("payment-check-payment-status", args=[transaction_id])
        )

        # Verify payment status response
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["status"], "succeeded")
        self.assertEqual(status_response.data["moyasar_id"], moyasar_payment_id)
        self.assertEqual(status_response.data["transaction_type"], "subscription")
