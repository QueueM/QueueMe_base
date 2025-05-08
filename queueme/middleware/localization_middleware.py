"""
Localization middleware for Queue Me platform.

This middleware automatically detects user language preferences (Arabic or English)
and sets the appropriate translation for the current request.
"""

import logging

from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class LocalizationMiddleware(MiddlewareMixin):
    """
    Middleware to handle localization between Arabic and English.

    This middleware performs language detection based on:
    1. 'lang' query parameter (highest priority)
    2. 'Accept-Language' header
    3. User profile preference if authenticated
    4. Default to settings.LANGUAGE_CODE
    """

    def process_request(self, request):
        """Set language for the current request"""
        # Get language from query parameter (if present)
        query_lang = request.GET.get("lang")

        # Get language from Accept-Language header
        header_lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        if header_lang:
            header_lang = header_lang.split(",")[0].strip().split("-")[0]

        # Get language from user profile (if authenticated)
        user_lang = None
        if hasattr(request, "user") and request.user.is_authenticated:
            # Try to get language preference from user profile or related model
            try:
                if hasattr(request.user, "language_preference"):
                    user_lang = request.user.language_preference
                # Check for customer profile if it exists
                elif hasattr(request.user, "customer") and hasattr(
                    request.user.customer, "language_preference"
                ):
                    user_lang = request.user.customer.language_preference
            except Exception as e:
                logger.debug(f"Failed to get user language preference: {e}")

        # Determine language, with priority order: query param > user profile > header > default
        lang_code = query_lang or user_lang or header_lang or settings.LANGUAGE_CODE

        # Ensure it's one of our supported languages
        supported_langs = [code for code, name in settings.LANGUAGES]
        if lang_code not in supported_langs:
            lang_code = settings.LANGUAGE_CODE

        # Set the language
        translation.activate(lang_code)
        request.LANGUAGE_CODE = lang_code

        # Store the detected language for this request
        request.detected_language = lang_code

        return None

    def process_response(self, request, response):
        """Set Content-Language header and deactivate translation"""
        # Set Content-Language header if not already set
        if not response.has_header("Content-Language") and hasattr(
            request, "LANGUAGE_CODE"
        ):
            response["Content-Language"] = request.LANGUAGE_CODE

        # Deactivate translation after response is generated
        translation.deactivate()

        return response
