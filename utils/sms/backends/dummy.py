"""
Dummy SMS backend for Queue Me platform.

This module provides a dummy SMS backend that logs messages without sending them,
useful for testing and environments where SMS should be disabled.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DummyBackend:
    """
    Dummy SMS backend that does nothing but log.

    Useful for testing or environments where SMS is disabled.
    """

    def send(
        self, phone_number: str, message: str, context: Optional[Dict] = None
    ) -> bool:
        """
        Log the SMS message without sending.

        Args:
            phone_number: Recipient phone number
            message: Message content
            context: Optional context for template rendering

        Returns:
            True (always succeeds)
        """
        logger.info(f"DUMMY SMS to {phone_number}: {message[:50]}...")
        return True
