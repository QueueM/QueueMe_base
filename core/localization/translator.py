"""
Translation utilities for the Queue Me platform.

This module provides utilities to help with translation between Arabic and English.
"""

import logging

from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def translate_text(text_en, text_ar=None):
    """
    Translate text based on current language.

    Args:
        text_en (str): English text
        text_ar (str): Arabic text (optional)

    Returns:
        str: Translated text based on current language
    """
    current_language = translation.get_language()

    if current_language == "ar" and text_ar:
        return text_ar

    return text_en


def get_translated_field(obj, field_name):
    """
    Get translated version of a field with language suffix.

    For fields with language suffix (e.g., name_en, name_ar), this
    returns the appropriate field based on current language.

    Args:
        obj: Object with translatable fields
        field_name (str): Base field name

    Returns:
        str: Value of the translated field
    """
    current_language = translation.get_language()

    # Try language-specific field first
    lang_field = f"{field_name}_{current_language}"

    # If the language-specific field exists and has a value, use it
    if hasattr(obj, lang_field) and getattr(obj, lang_field):
        return getattr(obj, lang_field)

    # Otherwise, try base field
    if hasattr(obj, field_name):
        return getattr(obj, field_name)

    # If base field also doesn't exist, try the other language
    other_lang = "en" if current_language == "ar" else "ar"
    other_lang_field = f"{field_name}_{other_lang}"

    if hasattr(obj, other_lang_field) and getattr(obj, other_lang_field):
        return getattr(obj, other_lang_field)

    # If nothing is found, return empty string
    logger.warning(f"No translation found for field {field_name} on {obj.__class__.__name__}")
    return ""


def get_localized_choices(choices):
    """
    Get localized choices for a model field.

    Args:
        choices (tuple): Tuple of (value, label) choices

    Returns:
        tuple: Localized choices
    """
    localized_choices = []
    for value, label in choices:
        localized_choices.append((value, _(label)))

    return tuple(localized_choices)


def translate_model_instance(instance, fields):
    """
    Create a dictionary with translated fields for a model instance.

    Args:
        instance: Model instance
        fields (list): List of field names to translate

    Returns:
        dict: Dictionary with translated fields
    """
    result = {}

    for field in fields:
        result[field] = get_translated_field(instance, field)

    return result


def get_time_format(is_arabic=False):
    """
    Get appropriate time format string based on language.

    Args:
        is_arabic (bool): Whether to use Arabic format

    Returns:
        str: Time format string
    """
    # Queue Me uses 12-hour AM/PM format for both languages
    if is_arabic:
        # Arabic time format with Arabic numerals
        return "h:mm a"  # This should be displayed with Arabic numerals in templates
    else:
        # English time format
        return "h:mm a"


def get_date_format(is_arabic=False):
    """
    Get appropriate date format string based on language.

    Args:
        is_arabic (bool): Whether to use Arabic format

    Returns:
        str: Date format string
    """
    if is_arabic:
        # Arabic date format (still using Gregorian calendar as specified in requirements)
        return "d MMM, yyyy"  # This should be displayed with Arabic numerals in templates
    else:
        # English date format
        return "d MMM, yyyy"
