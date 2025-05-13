"""
Twilio SMS backend for Queue Me platform.

This module provides an SMS backend that sends messages through the Twilio API.
"""

import logging
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class TwilioBackend:
    """
    SMS backend that sends messages through Twilio.

    Requires the twilio package to be installed and the following settings:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_FROM_NUMBER
    """

    def __init__(self, account_sid=None, auth_token=None, from_number=None):
        """
        Initialize the Twilio backend.

        Args:
            account_sid: Twilio account SID (optional)
            auth_token: Twilio auth token (optional)
            from_number: Sender phone number (optional)
        """
        # Get settings from parameters or settings
        self.account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self.auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self.from_number = from_number or getattr(settings, "TWILIO_FROM_NUMBER", None)

        # Check for required settings
        if not self.account_sid or not self.auth_token or not self.from_number:
            raise ValueError("Twilio settings not configured correctly")

        # Defer twilio import until needed
        try:
            from twilio.rest import Client

            self.client = Client(self.account_sid, self.auth_token)
        except ImportError:
            raise ImportError("Twilio package is required for TwilioBackend")

    def send(self, phone_number: str, message: str, context: Optional[Dict] = None) -> bool:
        """
        Send an SMS message through Twilio.

        Args:
            phone_number: Recipient phone number
            message: Message content
            context: Optional context for template rendering

        Returns:
            True if successful, False otherwise
        """
        try:
            # Format phone number (ensure it has + prefix)
            if not phone_number.startswith("+"):
                phone_number = f"+{phone_number}"

            # Send message
            message_obj = self.client.messages.create(
                body=message, from_=self.from_number, to=phone_number
            )

            # Log success
            logger.info(f"SMS sent to {phone_number} (SID: {message_obj.sid})")

            return True
        except Exception as e:
            # Log error
            logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
