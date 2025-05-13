# QueueMe Integration Tests

This directory contains integration tests for the QueueMe application, focusing on verifying that different system components work together correctly, especially third-party integrations.

## Test Coverage

The integration tests focus on the following critical system components:

1. **Payment Processing**: Tests integration with Moyasar payment gateway
2. **Notification System**: Tests Firebase push notifications, SMS, and email delivery
3. **Authentication**: Tests user authentication flows including OTP verification
4. **Booking System**: Tests the end-to-end booking process

## Prerequisites

- Python 3.8+
- Django
- Test database configured
- Environment variables for third-party services (or use TEST_MODE)

## Running the Tests

### Test Mode vs. Real Integration

Most tests have a `TEST_MODE` variable that can be set to:

- `True`: Use mocks for third-party APIs (default, faster, no real API calls)
- `False`: Test against real third-party APIs (requires valid API credentials)

### Running All Tests

```bash
# Navigate to project root
cd /path/to/queueme

# Run all integration tests
python -m unittest discover integration_tests
```

### Running Specific Test Suites

```bash
# Run payment integration tests
python -m unittest integration_tests.payment_integration_test

# Run notification integration tests
python -m unittest integration_tests.notification_integration_test
```

## Using Real External Services

To test against real external services:

1. Set `TEST_MODE = False` in the test file
2. Set the required environment variables:

```bash
# For payment tests
export MOYASAR_TEST_KEY="sk_test_xxxxxx"
export MOYASAR_TEST_PUBLISH_KEY="pk_test_xxxxxx"

# For notification tests
export FIREBASE_CREDENTIALS_PATH="/path/to/firebase-credentials.json"
export TWILIO_ACCOUNT_SID="ACxxxxx"
export TWILIO_AUTH_TOKEN="xxxxxx"
export FIREBASE_SMS_API_URL="https://your-firebase-function-url/send-sms"
export FIREBASE_SMS_API_KEY="your-firebase-function-key"
```

## Writing New Integration Tests

When adding new tests, follow these guidelines:

1. Create a new file named `<feature>_integration_test.py`
2. Include a `TEST_MODE` flag to allow running with mocks
3. Create mock classes for external services
4. Use transaction.atomic where appropriate to avoid test data persistence
5. Clean up test data in tearDown/tearDownClass methods

## Continuous Integration

These tests can be run in your CI/CD pipeline. For GitHub Actions, use:

```yaml
- name: Run Integration Tests
  run: |
    python -m unittest discover integration_tests
  env:
    DJANGO_SETTINGS_MODULE: queueme.settings.test
    TEST_MODE: "True"  # Use mocks in CI
```

## Troubleshooting

If tests fail, check:

1. Database connectivity
2. Environment variables
3. Internet connectivity (for real API tests)
4. API rate limits
5. Test data cleanup between runs

For test mode failures, ensure your mock implementations match the expected behavior of the real services.
