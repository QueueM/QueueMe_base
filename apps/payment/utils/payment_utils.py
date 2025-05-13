import hashlib
import hmac
import re
from decimal import Decimal


def format_amount(amount, currency="SAR"):
    """Format amount with currency symbol"""
    if currency == "SAR":
        return f"{amount:.2f} SAR"
    return f"{amount:.2f} {currency}"


def convert_to_halalas(amount):
    """Convert SAR amount to halalas (100 halalas = 1 SAR)"""
    if not amount:
        return 0
    return int(Decimal(amount) * 100)


def convert_from_halalas(halalas):
    """Convert halalas to SAR"""
    if not halalas:
        return Decimal("0.00")
    return Decimal(halalas) / 100


def mask_card_number(card_number):
    """Mask credit card number (keep first 6 and last 4 digits)"""
    if not card_number:
        return ""

    # Remove spaces and dashes
    card_number = re.sub(r"[\s-]", "", card_number)

    if len(card_number) <= 10:
        # If card number is short, just mask all but last 4
        return f"****{card_number[-4:]}"

    return f"{card_number[:6]}{'*' * (len(card_number) - 10)}{card_number[-4:]}"


def detect_card_brand(card_number):
    """Detect card brand from card number"""
    if not card_number:
        return "unknown"

    # Remove spaces and dashes
    card_number = re.sub(r"[\s-]", "", card_number)

    # Visa: Starts with 4
    if re.match(r"^4", card_number):
        return "visa"

    # Mastercard: Starts with 51-55 or 2221-2720
    if re.match(r"^5[1-5]", card_number) or re.match(
        r"^222[1-9]|^22[3-9]|^2[3-6]|^27[0-1]|^2720", card_number
    ):
        return "mastercard"

    # American Express: Starts with 34 or 37
    if re.match(r"^3[47]", card_number):
        return "amex"

    # Discover: Starts with 6011, 622126-622925, 644-649, 65
    if re.match(
        r"^6011|^65|^644|^645|^646|^647|^648|^649|^622(12[6-9]|1[3-9]|[2-8]|9[0-1][0-9]|92[0-5])",
        card_number,
    ):
        return "discover"

    # Mada (Saudi domestic cards): Typically follows BIN ranges specific to Saudi banks
    # This is a simplified check - in reality you'd check against a list of BINs
    if re.match(r"^9[0-9]{5}", card_number):
        return "mada"

    return "unknown"


def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature using HMAC"""
    if not payload or not signature or not secret:
        return False

    # Create the expected signature
    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Compare signatures
    return hmac.compare_digest(expected_signature, signature)
