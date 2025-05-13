"""
Firebase Cloud Messaging Service for QueueMe

Handles push notifications using Firebase Cloud Messaging (FCM)
"""

import json
import logging
import os

import firebase_admin
from django.conf import settings
from django.utils.translation import gettext as _
from firebase_admin import credentials, initialize_app, messaging

from ..models import NotificationChannel

logger = logging.getLogger("queueme.notifications")


class FirebaseNotificationService:
    """
    Service for sending push notifications using Firebase Cloud Messaging
    """

    _instance = None
    _initialized = False

    @classmethod
    def get_instance(cls):
        """
        Get a singleton instance of the Firebase service
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        Initialize the Firebase service with credentials from settings
        """
        if not FirebaseNotificationService._initialized:
            self._initialize_firebase()
            FirebaseNotificationService._initialized = True

    def _initialize_firebase(self):
        """
        Initialize Firebase SDK with credentials
        """
        try:
            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                initialize_app(cred)
                logger.info("Firebase initialized with credentials file")
            else:
                # Use environment variables if no credentials file exists
                firebase_config = {
                    "apiKey": settings.FIREBASE_API_KEY,
                    "projectId": settings.FIREBASE_PROJECT_ID,
                    "appId": settings.FIREBASE_APP_ID,
                    "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
                    "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
                }
                initialize_app(firebase_config)
                logger.info("Firebase initialized with environment settings")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self._initialized = False

    def send_notification(
        self,
        token,
        title,
        body,
        data=None,
        image_url=None,
        click_action=None,
        badge=None,
        sound=None,
        topic=None,
    ):
        """
        Send a push notification to a device or topic

        Args:
            token: Device token or topic name (prefixed with /topics/)
            title: Notification title
            body: Notification body text
            data: Additional data payload
            image_url: Optional URL for notification image
            click_action: Action to take when notification is clicked
            badge: Badge count (iOS)
            sound: Sound to play
            topic: Topic to send to (alternative to token)

        Returns:
            dict: Result of the notification send operation
        """
        try:
            # Initialize notification data
            notification = messaging.Notification(title=title, body=body)

            # Add image if provided
            if image_url:
                notification.image = image_url

            # Initialize message
            message = messaging.Message(
                notification=notification,
                token=token if not topic else None,
                topic=topic if topic else None,
                data=data or {},
            )

            # Add Android-specific configuration
            android_config = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_notification",
                    color="#3B82F6",
                    click_action=click_action,
                    sound=sound or "default",
                ),
            )
            message.android = android_config

            # Add iOS-specific configuration
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        badge=badge,
                        sound=sound or "default",
                        content_available=True,
                        mutable_content=True,
                        category="MESSAGE",
                    )
                )
            )
            message.apns = apns_config

            # Send the message
            response = messaging.send(message)

            logger.info(f"Successfully sent notification: {response}")
            return {"success": True, "message_id": response}

        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error sending notification: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {"success": False, "error": str(e)}

    def send_multicast(self, tokens, title, body, data=None, **kwargs):
        """
        Send a notification to multiple devices

        Args:
            tokens: List of device tokens
            title: Notification title
            body: Notification body text
            data: Additional data payload
            **kwargs: Additional arguments for notification

        Returns:
            dict: Result of the multicast send operation
        """
        try:
            # Initialize notification data
            notification = messaging.Notification(title=title, body=body)

            # Add image if provided
            if kwargs.get("image_url"):
                notification.image = kwargs.get("image_url")

            # Create multicast message
            multicast_message = messaging.MulticastMessage(
                notification=notification, tokens=tokens, data=data or {}
            )

            # Add Android-specific configuration
            android_config = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_notification",
                    color="#3B82F6",
                    click_action=kwargs.get("click_action"),
                    sound=kwargs.get("sound", "default"),
                ),
            )
            multicast_message.android = android_config

            # Add iOS-specific configuration
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        badge=kwargs.get("badge"),
                        sound=kwargs.get("sound", "default"),
                        content_available=True,
                        mutable_content=True,
                        category="MESSAGE",
                    )
                )
            )
            multicast_message.apns = apns_config

            # Send the multicast message
            response = messaging.send_multicast(multicast_message)

            logger.info(
                f"Multicast sent: {response.success_count} successful, {response.failure_count} failed"
            )
            return {
                "success": True,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error sending multicast: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error sending multicast: {str(e)}")
            return {"success": False, "error": str(e)}

    def subscribe_to_topic(self, tokens, topic):
        """
        Subscribe devices to a topic

        Args:
            tokens: List of device tokens
            topic: Topic name

        Returns:
            dict: Result of the subscribe operation
        """
        try:
            # Subscribe devices to topic
            response = messaging.subscribe_to_topic(tokens, topic)

            logger.info(
                f"Topic subscription: {response.success_count} successful, {response.failure_count} failed"
            )
            return {
                "success": True,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error subscribing to topic: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error subscribing to topic: {str(e)}")
            return {"success": False, "error": str(e)}

    def unsubscribe_from_topic(self, tokens, topic):
        """
        Unsubscribe devices from a topic

        Args:
            tokens: List of device tokens
            topic: Topic name

        Returns:
            dict: Result of the unsubscribe operation
        """
        try:
            # Unsubscribe devices from topic
            response = messaging.unsubscribe_from_topic(tokens, topic)

            logger.info(
                f"Topic unsubscription: {response.success_count} successful, {response.failure_count} failed"
            )
            return {
                "success": True,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error unsubscribing from topic: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error unsubscribing from topic: {str(e)}")
            return {"success": False, "error": str(e)}
