# Moyasar Payment Integration Guide for QueueMe

This guide provides comprehensive instructions for setting up and configuring Moyasar payment integration in the QueueMe platform, specifically designed for handling multiple payment wallets.

## Overview

QueueMe integrates with Moyasar payment gateway to handle three different types of payments:

1. **Subscription Payments**: For business subscriptions to QueueMe platform
2. **Advertisement Payments**: For businesses to purchase ad spaces
3. **Merchant Payments**: For end customers to pay for bookings and services

Each payment type uses a separate Moyasar wallet with its own set of API keys and configurations.

## Prerequisites

Before you begin, make sure you have:

1. A Moyasar account with access to the merchant dashboard
2. Three separate wallets (or sub-accounts) created in Moyasar for each payment type
3. API keys (publishable and secret) for each wallet
4. Webhook endpoints configured in Moyasar dashboard

## Environment Configuration

Add the following environment variables to your `.env` file:

```
# ──────────────────────────────────────────────────────────────────────────────
# Moyasar subscription wallet
# ──────────────────────────────────────────────────────────────────────────────
MOYASAR_SUB_PUBLIC=pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_SUB_SECRET=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_SUB_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MOYASAR_SUB_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/subscription/
MOYASAR_SUB_CALLBACK_URL_COMPLETE=https://queueme.net/payments/subscription/complete

# ──────────────────────────────────────────────────────────────────────────────
# Moyasar ads wallet
# ──────────────────────────────────────────────────────────────────────────────
MOYASAR_ADS_PUBLIC=pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_ADS_SECRET=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_ADS_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MOYASAR_ADS_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/ads/

# ──────────────────────────────────────────────────────────────────────────────
# Moyasar merchant wallet
# ──────────────────────────────────────────────────────────────────────────────
MOYASAR_MER_PUBLIC=pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_MER_SECRET=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOYASAR_MER_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MOYASAR_MER_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/merchant/
```

Replace all placeholder values with your actual Moyasar credentials.

## Testing Your Configuration

QueueMe includes a management command to check your Moyasar configuration. Run:

```bash
python manage.py check_moyasar_config
```

To also test the connection to Moyasar API:

```bash
python manage.py check_moyasar_config --test
```

## Webhook Setup in Moyasar Dashboard

Configure webhooks in the Moyasar dashboard for each wallet:

1. **Subscription Wallet**:
   - URL: `https://api.queueme.net/api/v1/payment/webhooks/subscription/`
   - Events: `payment.created`, `payment.paid`, `payment.failed`, `payment.refunded`

2. **Advertisement Wallet**:
   - URL: `https://api.queueme.net/api/v1/payment/webhooks/ads/`
   - Events: `payment.created`, `payment.paid`, `payment.failed`, `payment.refunded`

3. **Merchant Wallet**:
   - URL: `https://api.queueme.net/api/v1/payment/webhooks/merchant/`
   - Events: `payment.created`, `payment.paid`, `payment.failed`, `payment.refunded`

## Transaction Types

The system uses the following transaction types to route payments to the correct wallet:

- `subscription`: For business subscriptions
- `ad`: For advertisement purchases
- `booking`: For customer service bookings

When creating a payment, make sure to use the correct transaction type:

```python
result = PaymentService.create_payment(
    user_id=user.id,
    amount=100.00,  # Amount in SAR
    transaction_type="subscription",  # or "ad" or "booking"
    description="Monthly Premium Subscription",
    content_object=subscription,
    payment_type="card",
)
```

## Frontend Integration

### Getting the Appropriate Public Key

Frontend applications should request the appropriate public key for each transaction type:

```
GET /api/v1/payments/moyasar_public_key/?transaction_type=subscription
```

Response:
```json
{
    "transaction_type": "subscription",
    "public_key": "pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "wallet_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### Creating a Payment Form

Use the Moyasar JavaScript library to create payment forms. Example:

```javascript
// Get the public key for the transaction type
const response = await fetch('/api/v1/payments/moyasar_public_key/?transaction_type=subscription');
const data = await response.json();
const publicKey = data.public_key;

// Initialize Moyasar form
Moyasar.init({
    element: '#payment-form',
    amount: 10000, // Amount in halalas (100 SAR)
    currency: 'SAR',
    description: 'Premium Subscription',
    publishable_api_key: publicKey,
    callback_url: 'https://queueme.net/payments/subscription/complete',
    methods: ['creditcard', 'stcpay', 'applepay']
});
```

## Currency Handling

Moyasar accepts amounts in halalas (100 halalas = 1 SAR). The `Payment` service automatically converts:

- When creating a payment transaction, you provide amount in SAR (e.g., `100.00`)
- The system automatically converts to halalas (e.g., `10000`) before sending to Moyasar

## Handling Payments in Production

### SSL Requirements

Moyasar requires all API calls and webhooks to use HTTPS. Ensure your domains have valid SSL certificates.

### Changing to Production Mode

When moving to production:

1. Update all API keys to production keys (starting with `pk_live_` and `sk_live_`)
2. Update webhook endpoints in the Moyasar dashboard
3. Update callback URLs to production domains

### Security Considerations

1. Never expose secret keys to client-side code
2. Implement rate limiting on payment endpoints to prevent abuse
3. Use webhook signing to verify that webhook calls originate from Moyasar
4. Store transaction data securely and encrypt sensitive information

## Troubleshooting

Common issues and solutions:

### Wallet Misconfiguration

If payments are failing, check the wallet configuration:

```bash
python manage.py check_moyasar_config --test
```

### Webhook Issues

If webhooks aren't being received:

1. Check the webhook configuration in Moyasar dashboard
2. Verify HTTPS is properly configured
3. Check server logs for webhook requests
4. Ensure the webhook endpoint is publicly accessible

### Handling Successful Payments

When a payment succeeds:

1. The webhook will update the transaction status to "succeeded"
2. The system will call `PaymentService.handle_successful_payment`
3. The related object (subscription, ad, booking) will be updated

## API References

For more details, refer to the Moyasar API documentation:
- [Moyasar API Docs](https://docs.moyasar.com/)
- [QueueMe API Docs](https://api.queueme.net/api/docs/)
