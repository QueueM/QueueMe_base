"""
SMS sending functionality for Queue Me platform.

This module provides a central function for sending SMS messages through
configurable backends.
"""

import importlib
import logging
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(
    phone_number: str,
    message: str,
    context: Optional[Dict] = None,
    backend: Optional[str] = None,
    fail_silently: bool = False,
) -> bool:
    """
    Send an SMS message using the configured backend.

    Args:
        phone_number: Recipient phone number
        message: Message content
        context: Optional context for template rendering
        backend: Optional backend path override
        fail_silently: Whether to suppress exceptions

    Returns:
        True if successful, False otherwise
    """
    if not phone_number or not message:
        if fail_silently:
            return False
        raise ValueError("Phone number and message are required")

    # Determine backend to use
    if not backend:
        backend = getattr(settings, "SMS_BACKEND", "utils.sms.backends.dummy.DummyBackend")

    try:
        # Dynamically import the backend class
        module_path, class_name = backend.rsplit(".", 1)
        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)

        # Initialize the backend
        backend_instance = backend_class()

        # Send the message
        return backend_instance.send(phone_number, message, context=context)
    except (ImportError, AttributeError) as e:
        logger.error(f"Error loading SMS backend '{backend}': {str(e)}")
        if fail_silently:
            return False
        raise
    except Exception as e:
        logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
        if fail_silently:
            return False
        raise
