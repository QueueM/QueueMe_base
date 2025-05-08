"""
Language detection utilities for the Queue Me platform.

This module provides functions to detect and set the user's preferred language.
"""

import logging

from django.conf import settings
from django.utils import translation

logger = logging.getLogger(__name__)


def detect_language_from_request(request):
    """
    Detect language from request.

    Order of precedence:
    1. Language query parameter ('lang')
    2. Accept-Language header
    3. User preference (if logged in)
    4. Default language (from settings)

    Args:
        request: The HTTP request

    Returns:
        str: Language code ('en' or 'ar')
    """
    # Check query parameter first
    query_lang = request.GET.get("lang")
    if query_lang in [lang[0] for lang in settings.LANGUAGES]:
        logger.debug(f"Language detected from query parameter: {query_lang}")
        return query_lang

    # Check Accept-Language header
    accept_lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    if accept_lang:
        # Extract first language code
        lang_code = accept_lang.split(",")[0].strip().split("-")[0]
        if lang_code in [lang[0] for lang in settings.LANGUAGES]:
            logger.debug(f"Language detected from Accept-Language header: {lang_code}")
            return lang_code

    # Check user preference if authenticated
    if hasattr(request, "user") and request.user.is_authenticated:
        try:
            if hasattr(request.user, "language_preference"):
                user_lang = request.user.language_preference
                if user_lang in [lang[0] for lang in settings.LANGUAGES]:
                    logger.debug(f"Language detected from user preference: {user_lang}")
                    return user_lang
        except AttributeError:
            pass

    # Default to settings
    default_lang = settings.LANGUAGE_CODE
    logger.debug(f"Using default language: {default_lang}")
    return default_lang


def set_language_for_request(request):
    """
    Set language for the current request.

    Args:
        request: The HTTP request

    Returns:
        str: The language code that was set
    """
    lang_code = detect_language_from_request(request)
    translation.activate(lang_code)
    request.LANGUAGE_CODE = lang_code
    return lang_code


def get_language_from_header(accept_language_header):
    """
    Parse language from Accept-Language header.

    Args:
        accept_language_header (str): Accept-Language header value

    Returns:
        str: Language code or None
    """
    if not accept_language_header:
        return None

    # Split the header and extract the first language code
    for lang_item in accept_language_header.split(","):
        if not lang_item:
            continue

        # Extract the language code (before quality value if present)
        lang_code = lang_item.split(";")[0].strip().split("-")[0]

        # Check if it's a supported language
        if lang_code in [lang[0] for lang in settings.LANGUAGES]:
            return lang_code

    return None


def is_rtl(language_code):
    """
    Check if language is right-to-left.

    Args:
        language_code (str): Language code

    Returns:
        bool: True if RTL language
    """
    # In Queue Me, only Arabic is RTL
    return language_code == "ar"


def get_text_direction(language_code=None):
    """
    Get text direction for a language.

    Args:
        language_code (str): Language code (default: current language)

    Returns:
        str: 'rtl' or 'ltr'
    """
    language_code = language_code or translation.get_language()
    return "rtl" if is_rtl(language_code) else "ltr"
