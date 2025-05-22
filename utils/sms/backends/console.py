"""
Console SMS backend for Queue Me platform.

This module provides an SMS backend that prints messages to the console,
useful for development and testing.
"""

import logging
import sys
from typing import Dict, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class ConsoleBackend:
    """
    SMS backend that writes messages to the console/stdout.

    Useful for development and testing without sending real SMS messages.
    """

    def __init__(self, stream=None):
        """
        Initialize the console backend.

        Args:
            stream: Output stream (defaults to stdout)
        """
        self.stream = stream or sys.stdout

    def send(
        self, phone_number: str, message: str, context: Optional[Dict] = None
    ) -> bool:
        """
        Print the SMS message to the console.

        Args:
            phone_number: Recipient phone number
            message: Message content
            context: Optional context for template rendering

        Returns:
            True (always succeeds)
        """
        # Format the output
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        output = (
            f"\n----- SMS Message at {timestamp} -----\n"
            f"To: {phone_number}\n"
            f"Message:\n{message}\n"
            f"----------------------------------\n"
        )

        # Write to stream
        self.stream.write(output)
        self.stream.flush()

        # Log the action
        logger.debug(f"SMS to {phone_number} sent to console")

        return True
