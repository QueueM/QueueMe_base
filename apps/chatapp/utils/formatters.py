import html
import re

from django.utils import timezone


def format_message_time(timestamp, use_24h=False):
    """
    Format timestamp in AM/PM or 24-hour format

    Parameters:
    - timestamp: Datetime object
    - use_24h: Whether to use 24-hour format

    Returns:
    - Formatted timestamp string
    """
    if not timestamp:
        return ""

    if use_24h:
        return timestamp.strftime("%H:%M - %d %b, %Y")
    else:
        return timestamp.strftime("%I:%M %p - %d %b, %Y")


def format_last_seen(timestamp):
    """
    Format last seen timestamp in a user-friendly way

    Parameters:
    - timestamp: Datetime object

    Returns:
    - User-friendly string (e.g., "Just now", "5 minutes ago", "Yesterday")
    """
    if not timestamp:
        return "Unknown"

    now = timezone.now()
    diff = now - timestamp

    # Calculate difference in seconds
    diff_seconds = diff.total_seconds()

    if diff_seconds < 60:
        return "Just now"
    elif diff_seconds < 3600:
        minutes = int(diff_seconds // 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif diff_seconds < 86400:
        hours = int(diff_seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff_seconds < 172800:
        return "Yesterday"
    elif diff_seconds < 604800:
        days = int(diff_seconds // 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    else:
        return timestamp.strftime("%d %b, %Y")


def sanitize_html(text):
    """
    Sanitize HTML to prevent XSS attacks

    Parameters:
    - text: Text that might contain HTML

    Returns:
    - Sanitized text
    """
    if not text:
        return ""

    # Escape HTML entities
    text = html.escape(text)

    return text


def linkify_text(text):
    """
    Convert URLs in text to clickable links

    Parameters:
    - text: Plain text

    Returns:
    - Text with URLs converted to HTML links
    """
    if not text:
        return ""

    # URL pattern
    url_pattern = r"(https?://[^\s]+)"

    # Replace URLs with HTML links
    text = re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text)

    return text


def truncate_text(text, max_length=50, suffix="..."):
    """
    Truncate text to a maximum length

    Parameters:
    - text: Text to truncate
    - max_length: Maximum length
    - suffix: Suffix to add if truncated

    Returns:
    - Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length] + suffix
