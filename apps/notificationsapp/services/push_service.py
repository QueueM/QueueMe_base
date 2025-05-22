import logging
from typing import Any, Dict, List, Optional

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

from apps.notificationsapp.models import DeviceToken

logger = logging.getLogger(__name__)


class PushService:
    """
    Service for sending push notifications to different platforms (iOS, Android, Web).
    Handles device token management, payload formatting, and delivery tracking.
    """

    @staticmethod
    def send_push_notification(user, title, body, data=None, badge=None, sound=None):
        """
        Send push notification to all devices for a user.

        Args:
            user: User to send to
            title: Notification title
            body: Notification body
            data: Optional data payload
            badge: Optional badge number (for iOS)
            sound: Optional sound to play

        Returns:
            Dict with success count per platform
        """
        if data is None:
            data = {}

        # Get all active device tokens for this user
        device_tokens = DeviceToken.objects.filter(user=user, is_active=True)

        # Group tokens by platform
        ios_tokens = []
        android_tokens = []
        web_tokens = []

        for device in device_tokens:
            if device.platform == "ios":
                ios_tokens.append(device.token)
            elif device.platform == "android":
                android_tokens.append(device.token)
            elif device.platform == "web":
                web_tokens.append(device.token)

        results = {"ios": 0, "android": 0, "web": 0}

        # Send to iOS devices
        if ios_tokens:
            ios_results = PushService.send_apns(
                tokens=ios_tokens,
                title=title,
                body=body,
                data=data,
                badge=badge,
                sound=sound,
            )
            results["ios"] = ios_results.get("success", 0)

        # Send to Android devices
        if android_tokens:
            android_results = PushService.send_fcm(
                tokens=android_tokens, title=title, body=body, data=data, sound=sound
            )
            results["android"] = android_results.get("success", 0)

        # Send to Web devices
        if web_tokens:
            web_results = PushService.send_web_push(
                tokens=web_tokens, title=title, body=body, data=data
            )
            results["web"] = web_results.get("success", 0)

        return results

    @staticmethod
    def send_apns(tokens, title, body, data=None, badge=None, sound=None):
        """
        Send Apple Push Notification Service (APNS) messages.

        Args:
            tokens: List of device tokens
            title: Notification title
            body: Notification body
            data: Optional data payload
            badge: Optional badge number
            sound: Optional sound to play

        Returns:
            Dict with success and failure counts
        """
        try:
            # This is a placeholder implementation
            # In a real implementation, you'd use a library like aioapns or apns2

            logger.info(f"Would send APNS to {len(tokens)} devices: {title}")

            # Example with apns2:
            # from apns2.client import APNsClient
            # from apns2.payload import Payload
            # from apns2.errors import APNsException

            # client = APNsClient(
            #     credentials=settings.APNS_CERT_PATH,
            #     use_sandbox=settings.APNS_USE_SANDBOX
            # )

            # payload = Payload(
            #     alert={'title': title, 'body': body},
            #     badge=badge,
            #     sound=sound or "default",
            #     custom=data
            # )

            # topic = settings.APNS_TOPIC
            # success = 0
            # failed = 0

            # for token in tokens:
            #     try:
            #         result = client.send_notification(token, payload, topic)
            #         success += 1
            #     except APNsException as e:
            #         failed += 1
            #         logger.error(f"APNS error for token {token}: {str(e)}")

            # return {
            #     'success': success,
            #     'failed': failed,
            #     'total': len(tokens)
            # }

            # Simulate successful sending
            return {"success": len(tokens), "failed": 0, "total": len(tokens)}

        except Exception as e:
            logger.error(f"Error sending APNS: {str(e)}")
            return {
                "success": 0,
                "failed": len(tokens),
                "total": len(tokens),
                "error": str(e),
            }

    @staticmethod
    def send_fcm(tokens, title, body, data=None, sound=None):
        """
        Send Firebase Cloud Messaging (FCM) messages.

        Args:
            tokens: List of device tokens
            title: Notification title
            body: Notification body
            data: Optional data payload
            sound: Optional sound to play

        Returns:
            Dict with success and failure counts
        """
        try:
            # This is a placeholder implementation
            # In a real implementation, you'd use the firebase-admin library

            logger.info(f"Would send FCM to {len(tokens)} devices: {title}")

            # Example:
            # from firebase_admin import messaging
            #
            # notification = messaging.Notification(
            #     title=title,
            #     body=body
            # )
            #
            # android = messaging.AndroidConfig(
            #     priority='high',
            #     notification=messaging.AndroidNotification(
            #         sound=sound or 'default'
            #     )
            # )
            #
            # apns = messaging.APNSConfig(
            #     payload=messaging.APNSPayload(
            #         aps=messaging.Aps(
            #             sound=sound or 'default'
            #         )
            #     )
            # )
            #
            # fcm_message = messaging.MulticastMessage(
            #     notification=notification,
            #     data=data,
            #     android=android,
            #     apns=apns,
            #     tokens=tokens
            # )
            #
            # response = messaging.send_multicast(fcm_message)
            #
            # return {
            #     'success': response.success_count,
            #     'failed': response.failure_count,
            #     'total': len(tokens)
            # }

            # Simulate successful sending
            return {"success": len(tokens), "failed": 0, "total": len(tokens)}

        except Exception as e:
            logger.error(f"Error sending FCM: {str(e)}")
            return {
                "success": 0,
                "failed": len(tokens),
                "total": len(tokens),
                "error": str(e),
            }

    @staticmethod
    def send_web_push(tokens, title, body, data=None):
        """
        Send Web Push notifications.

        Args:
            tokens: List of device tokens (subscription objects)
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            Dict with success and failure counts
        """
        try:
            # This is a placeholder implementation
            # In a real implementation, you'd use the pywebpush library

            logger.info(f"Would send Web Push to {len(tokens)} devices: {title}")

            # Example:
            # from pywebpush import webpush, WebPushException
            #
            # success = 0
            # failed = 0
            #
            # payload = json.dumps({
            #     'title': title,
            #     'body': body,
            #     'data': data
            # })
            #
            # for token_json in tokens:
            #     try:
            #         subscription_info = json.loads(token_json)
            #         webpush(
            #             subscription_info=subscription_info,
            #             data=payload,
            #             vapid_private_key=settings.VAPID_PRIVATE_KEY,
            #             vapid_claims={
            #                 'sub': f'mailto:{settings.VAPID_CLAIM_EMAIL}'
            #             }
            #         )
            #         success += 1
            #     except WebPushException as e:
            #         failed += 1
            #         logger.error(f"Web Push error: {str(e)}")
            #
            # return {
            #     'success': success,
            #     'failed': failed,
            #     'total': len(tokens)
            # }

            # Simulate successful sending
            return {"success": len(tokens), "failed": 0, "total": len(tokens)}

        except Exception as e:
            logger.error(f"Error sending Web Push: {str(e)}")
            return {
                "success": 0,
                "failed": len(tokens),
                "total": len(tokens),
                "error": str(e),
            }

    @staticmethod
    def register_device(user, token, platform, device_id):
        """
        Register a device token for push notifications.

        Args:
            user: User to associate with the token
            token: Device token
            platform: Device platform (ios, android, web)
            device_id: Unique device identifier

        Returns:
            DeviceToken object or None on error
        """
        try:
            # Update existing token if it exists
            device, created = DeviceToken.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={"token": token, "platform": platform, "is_active": True},
            )

            return device

        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
            return None

    @staticmethod
    def deactivate_device(user, device_id=None, token=None):
        """
        Deactivate a device token.

        Args:
            user: User associated with the token
            device_id: Optional device identifier
            token: Optional token value

        Returns:
            Boolean indicating success
        """
        try:
            if not (device_id or token):
                return False

            query = DeviceToken.objects.filter(user=user)

            if device_id:
                query = query.filter(device_id=device_id)

            if token:
                query = query.filter(token=token)

            count = query.update(is_active=False)

            return count > 0

        except Exception as e:
            logger.error(f"Error deactivating device: {str(e)}")
            return False


class FirebasePushService:
    """
    Service for sending push notifications via Firebase Cloud Messaging.
    """

    _initialized = False

    @classmethod
    def _initialize(cls):
        """Initialize Firebase if not already initialized."""
        if cls._initialized:
            return

        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
            cls._initialized = True
        except ValueError:
            # Initialize Firebase
            try:
                cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
                if cred_path:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    # Initialize with default config for testing
                    firebase_admin.initialize_app()
                cls._initialized = True
                logger.info("Firebase initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {str(e)}")
                raise

    @classmethod
    def send_notification(
        cls,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a push notification to the specified device tokens.

        Args:
            tokens: List of FCM tokens to send notification to
            title: Title of the notification
            body: Body text of the notification
            data: Additional data payload to send with notification

        Returns:
            Dictionary with the result of the operation
        """
        if not tokens:
            return {"success": False, "error": "No tokens provided"}

        try:
            cls._initialize()

            # Create message
            notification = messaging.Notification(
                title=title,
                body=body,
            )

            results = []

            # Send to each token (can be batched for multiple tokens in production)
            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=notification,
                        data=data or {},
                        token=token,
                    )

                    # Send message
                    response = messaging.send(message)
                    results.append(
                        {"token": token, "message_id": response, "success": True}
                    )
                except messaging.ApiCallError as e:
                    results.append({"token": token, "error": str(e), "success": False})

            # Calculate success and failure
            success_count = sum(1 for r in results if r.get("success", False))
            failure_count = len(results) - success_count

            return {
                "success": success_count > 0,
                "success_count": success_count,
                "failure_count": failure_count,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return {"success": False, "error": str(e)}

    @classmethod
    def send_data_message(
        cls,
        tokens: List[str],
        data: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Send a data-only message to the specified device tokens.

        Args:
            tokens: List of FCM tokens to send message to
            data: Data payload to send

        Returns:
            Dictionary with the result of the operation
        """
        if not tokens:
            return {"success": False, "error": "No tokens provided"}

        try:
            cls._initialize()

            results = []

            # Send to each token
            for token in tokens:
                try:
                    message = messaging.Message(
                        data=data,
                        token=token,
                    )

                    # Send message
                    response = messaging.send(message)
                    results.append(
                        {"token": token, "message_id": response, "success": True}
                    )
                except messaging.ApiCallError as e:
                    results.append({"token": token, "error": str(e), "success": False})

            # Calculate success and failure
            success_count = sum(1 for r in results if r.get("success", False))
            failure_count = len(results) - success_count

            return {
                "success": success_count > 0,
                "success_count": success_count,
                "failure_count": failure_count,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error sending data message: {str(e)}")
            return {"success": False, "error": str(e)}

    @classmethod
    def send_topic_message(
        cls,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to a topic.

        Args:
            topic: Topic name to send to
            title: Title of the notification
            body: Body text of the notification
            data: Additional data payload to send with notification

        Returns:
            Dictionary with the result of the operation
        """
        try:
            cls._initialize()

            # Create message
            notification = messaging.Notification(
                title=title,
                body=body,
            )

            condition = f"'${topic}' in topics"

            message = messaging.Message(
                notification=notification,
                data=data or {},
                condition=condition,
            )

            # Send message
            response = messaging.send(message)

            return {
                "success": True,
                "message_id": response,
            }

        except Exception as e:
            logger.error(f"Error sending topic notification: {str(e)}")
            return {"success": False, "error": str(e)}
