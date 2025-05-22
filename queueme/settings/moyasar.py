"""
Moyasar Payment Gateway Configuration

This module defines the configuration for the three Moyasar payment wallets:
1. Subscription wallet - For company subscriptions to QueueMe platform
2. Ads wallet - For companies buying advertising space on QueueMe
3. Merchant wallet - For customer payments to shops for services/bookings
"""

import os

# Subscription wallet configuration
MOYASAR_SUB = {
    "PUBLIC_KEY": os.environ.get("MOYASAR_SUB_PUBLIC", ""),
    "SECRET_KEY": os.environ.get("MOYASAR_SUB_SECRET", ""),
    "WALLET_ID": os.environ.get("MOYASAR_SUB_WALLET_ID", ""),
    "CALLBACK_URL": os.environ.get(
        "MOYASAR_SUB_CALLBACK_URL",
        "https://api.queueme.net/api/v1/payment/webhooks/subscription/",
    ),
    "CALLBACK_COMPLETE_URL": os.environ.get(
        "MOYASAR_SUB_CALLBACK_URL_COMPLETE",
        "https://queueme.net/payments/subscription/complete",
    ),
}

# Ads wallet configuration
MOYASAR_ADS = {
    "PUBLIC_KEY": os.environ.get("MOYASAR_ADS_PUBLIC", ""),
    "SECRET_KEY": os.environ.get("MOYASAR_ADS_SECRET", ""),
    "WALLET_ID": os.environ.get("MOYASAR_ADS_WALLET_ID", ""),
    "CALLBACK_URL": os.environ.get(
        "MOYASAR_ADS_CALLBACK_URL",
        "https://api.queueme.net/api/v1/payment/webhooks/ads/",
    ),
}

# Merchant wallet configuration
MOYASAR_MER = {
    "PUBLIC_KEY": os.environ.get("MOYASAR_MER_PUBLIC", ""),
    "SECRET_KEY": os.environ.get("MOYASAR_MER_SECRET", ""),
    "WALLET_ID": os.environ.get("MOYASAR_MER_WALLET_ID", ""),
    "CALLBACK_URL": os.environ.get(
        "MOYASAR_MER_CALLBACK_URL",
        "https://api.queueme.net/api/v1/payment/webhooks/merchant/",
    ),
}


def validate_moyasar_config():
    """
    Validate the Moyasar configuration for all three wallets

    Returns:
        dict: Configuration status with missing and empty keys
    """
    # Required keys for each wallet
    required_keys = ["PUBLIC_KEY", "SECRET_KEY", "WALLET_ID", "CALLBACK_URL"]

    missing_keys = []
    empty_keys = []

    # Check subscription wallet
    for key in required_keys:
        if key not in MOYASAR_SUB:
            missing_keys.append(f"MOYASAR_SUB_{key}")
        elif not MOYASAR_SUB[key]:
            empty_keys.append(f"MOYASAR_SUB_{key}")

    # Check ads wallet
    for key in required_keys:
        if key not in MOYASAR_ADS:
            missing_keys.append(f"MOYASAR_ADS_{key}")
        elif not MOYASAR_ADS[key]:
            empty_keys.append(f"MOYASAR_ADS_{key}")

    # Check merchant wallet
    for key in required_keys:
        if key not in MOYASAR_MER:
            missing_keys.append(f"MOYASAR_MER_{key}")
        elif not MOYASAR_MER[key]:
            empty_keys.append(f"MOYASAR_MER_{key}")

    # Check if all wallets have the required keys configured
    wallet_status = {
        "subscription": bool(
            MOYASAR_SUB["PUBLIC_KEY"]
            and MOYASAR_SUB["SECRET_KEY"]
            and MOYASAR_SUB["WALLET_ID"]
        ),
        "ads": bool(
            MOYASAR_ADS["PUBLIC_KEY"]
            and MOYASAR_ADS["SECRET_KEY"]
            and MOYASAR_ADS["WALLET_ID"]
        ),
        "merchant": bool(
            MOYASAR_MER["PUBLIC_KEY"]
            and MOYASAR_MER["SECRET_KEY"]
            and MOYASAR_MER["WALLET_ID"]
        ),
    }

    return {
        "missing_keys": missing_keys,
        "empty_keys": empty_keys,
        "wallet_status": wallet_status,
    }


# Configuration constants
MOYASAR_BASE_URL = "https://api.moyasar.com/v1"
