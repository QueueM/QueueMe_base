# Data conversion utilities


def to_halalas(riyals):
    """Convert SAR to halalas (1 SAR = 100 halalas)"""
    try:
        return int(float(riyals) * 100)
    except (ValueError, TypeError):
        return 0


def to_riyals(halalas):
    """Convert halalas to SAR (100 halalas = 1 SAR)"""
    try:
        return float(halalas) / 100
    except (ValueError, TypeError):
        return 0.0


def format_phone_number(number):
    """Format phone number for consistent display"""
    if not number:
        return ""

    # Remove non-digit characters except leading +
    if number.startswith("+"):
        cleaned = "+" + "".join(c for c in number[1:] if c.isdigit())
    else:
        cleaned = "".join(c for c in number if c.isdigit())

    # Format Saudi numbers
    if cleaned.startswith("966") and len(cleaned) == 12:
        return f"+{cleaned[:3]} {cleaned[3:5]} {cleaned[5:8]} {cleaned[8:]}"
    elif cleaned.startswith("05") and len(cleaned) == 10:
        return f"{cleaned[:2]} {cleaned[2:5]} {cleaned[5:8]} {cleaned[8:]}"

    return cleaned
