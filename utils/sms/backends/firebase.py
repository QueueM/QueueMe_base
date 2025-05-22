"""
Firebase SMS Backend for QueueMe

This backend uses Firebase Cloud Functions to send SMS messages,
replacing the Twilio backend.
"""

import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("queueme.sms")


class FirebaseSMSBackend:
    """
    An SMS backend that uses Firebase Cloud Functions for sending SMS
    """

    def __init__(self):
        """Initialize the Firebase SMS backend with credentials from settings"""
        self.api_url = getattr(settings, "FIREBASE_SMS_API_URL", None)
        self.api_key = getattr(settings, "FIREBASE_SMS_API_KEY", None)

        if not self.api_url:
            raise ImproperlyConfigured(
                "FIREBASE_SMS_API_URL must be set to use Firebase SMS backend"
            )

        if not self.api_key:
            raise ImproperlyConfigured(
                "FIREBASE_SMS_API_KEY must be set to use Firebase SMS backend"
            )

    def send_message(self, to, body, from_=None, **kwargs):
        """
        Send an SMS message using Firebase Functions

        Args:
            to: Recipient phone number (with country code)
            body: Message text
            from_: Sender identifier (ignored for Firebase)
            **kwargs: Additional parameters

        Returns:
            dict: Send result with success flag and message ID
        """
        try:
            # Clean phone number format (remove spaces, dashes, etc.)
            to = to.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

            # Ensure phone number starts with '+'
            if not to.startswith("+"):
                to = f"+{to}"

            # Prepare the request payload
            payload = {
                "to": to,
                "message": body,
                "region": kwargs.get("region", "SA"),  # Default to Saudi Arabia
            }

            # Add optional parameters if provided
            if kwargs.get("template_id"):
                payload["template_id"] = kwargs.get("template_id")

            if kwargs.get("template_data"):
                payload["template_data"] = kwargs.get("template_data")

            # Prepare headers with API key
            headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}

            # Make the request to Firebase Function
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )

            # Parse the response
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"SMS sent successfully to {to}")
                    return {
                        "success": True,
                        "message_id": result.get("message_id", ""),
                        "status": result.get("status", "sent"),
                    }
                else:
                    logger.error(f"Failed to send SMS to {to}: {result.get('error')}")
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                        "status": "failed",
                    }
            else:
                logger.error(
                    f"Firebase SMS API error: HTTP {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "status": "failed",
                }

        except requests.RequestException as e:
            logger.error(f"Network error when sending SMS: {str(e)}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "status": "failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error when sending SMS: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "status": "failed",
            }

    def send_bulk_messages(self, messages, **kwargs):
        """
        Send multiple SMS messages in bulk

        Args:
            messages: List of message dictionaries with 'to' and 'body'
            **kwargs: Additional parameters

        Returns:
            list: List of send results for each message
        """
        results = []

        for message in messages:
            to = message.get("to")
            body = message.get("body")

            if not to or not body:
                results.append(
                    {
                        "success": False,
                        "error": "Missing required fields (to, body)",
                        "status": "failed",
                    }
                )
                continue

            result = self.send_message(to=to, body=body, **kwargs)

            results.append(result)

        return results
