# apps/discountapp/utils/code_generator.py
import random
import string

from django.utils.crypto import get_random_string

from apps.discountapp.constants import (
    DEFAULT_COUPON_LENGTH,
    DEFAULT_COUPON_PREFIX,
    MAX_COUPON_CODE_LENGTH,
)


def generate_coupon_code(prefix=DEFAULT_COUPON_PREFIX, length=DEFAULT_COUPON_LENGTH):
    """
    Generate a random coupon code with prefix
    Format: PREFIX-RANDOMCHARS
    """
    # Ensure prefix is uppercase
    prefix = prefix.upper().strip()

    # Calculate random part length (subtract prefix length and 1 for the dash)
    random_length = max(4, min(MAX_COUPON_CODE_LENGTH - len(prefix) - 1, length))

    # Generate random part (uppercase letters and numbers)
    characters = string.ascii_uppercase + string.digits
    random_part = "".join(random.choice(characters) for _ in range(random_length))

    # Combine prefix and random part
    code = f"{prefix}-{random_part}"

    return code


def generate_batch_coupon_codes(
    prefix=DEFAULT_COUPON_PREFIX, length=DEFAULT_COUPON_LENGTH, quantity=1
):
    """
    Generate a batch of unique coupon codes
    """
    codes = set()

    # Generate more codes than needed to account for potential duplicates
    attempts = 0
    max_attempts = quantity * 2

    while len(codes) < quantity and attempts < max_attempts:
        code = generate_coupon_code(prefix, length)
        codes.add(code)
        attempts += 1

    # If we couldn't generate enough unique codes, adjust strategy
    if len(codes) < quantity:
        remaining = quantity - len(codes)
        # Add a unique hash to the prefix
        unique_prefix = f"{prefix}{get_random_string(2, allowed_chars='0123456789')}"

        for _ in range(remaining):
            code = generate_coupon_code(unique_prefix, length)
            codes.add(code)

    return list(codes)
