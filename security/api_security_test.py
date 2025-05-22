#!/usr/bin/env python
"""
API Security Testing Script for QueueMe

This script tests the security of API endpoints by conducting:
1. Authentication bypasses
2. Authorization checks
3. Input validation
4. Rate limiting checks
5. CSRF protections
"""

import json
import os
import random
import time

import requests

# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
TEST_USER_PHONE = os.environ.get("TEST_USER_PHONE", "+9665XXXXXXXX")
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "TestPass123!")
ADMIN_USER_PHONE = os.environ.get("ADMIN_USER_PHONE", "+9665XXXXXXXX")
ADMIN_USER_PASSWORD = os.environ.get("ADMIN_USER_PASSWORD", "AdminPass123!")

# Results storage
security_issues = []


def add_issue(severity, endpoint, title, details, recommendation):
    """Add an API security issue to the list"""
    security_issues.append(
        {
            "severity": severity,
            "endpoint": endpoint,
            "title": title,
            "details": details,
            "recommendation": recommendation,
        }
    )


def login(phone, password):
    """Get an auth token by logging in"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login/",
            json={"phone_number": phone, "password": password},
        )

        if response.status_code == 200:
            token = response.json().get("token")
            return token
        else:
            print(f"Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {str(e)}")
        return None


def test_authentication_bypasses():
    """Test for authentication bypass vulnerabilities"""
    print("Testing authentication bypasses...")

    # List of protected endpoints to test
    protected_endpoints = [
        "/bookings/my-bookings/",
        "/payments/history/",
        "/payments/methods/",
        "/users/profile/",
        "/notifications/",
    ]

    # Test accessing protected endpoints without authentication
    for endpoint in protected_endpoints:
        response = requests.get(f"{API_BASE_URL}{endpoint}")

        if (
            response.status_code < 400
        ):  # Any 2XX or 3XX response indicates potential bypass
            add_issue(
                "critical",
                endpoint,
                "Authentication bypass possible",
                f"Endpoint {endpoint} returned status {response.status_code} without authentication",
                "Ensure all protected endpoints verify authentication using a middleware or decorator",
            )
        # Otherwise it's correctly rejecting the request


def test_authorization_bypasses(user_token, admin_token):
    """Test for authorization bypass vulnerabilities"""
    print("Testing authorization bypasses...")

    # Test accessing admin-only endpoints with normal user token
    admin_endpoints = [
        "/admin/shops/",
        "/admin/users/",
        "/admin/statistics/",
        "/admin/payments/",
    ]

    headers = {"Authorization": f"Token {user_token}"}

    for endpoint in admin_endpoints:
        response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)

        # Any 2XX response indicates a potential bypass
        if response.status_code >= 200 and response.status_code < 300:
            add_issue(
                "critical",
                endpoint,
                "Authorization bypass possible",
                f"Non-admin user can access admin endpoint {endpoint}",
                "Implement proper role-based access control for all admin endpoints",
            )

    # Test accessing another user's data
    # Note: This assumes IDs are UUIDs which are not easily guessable
    # Try with random UUIDs
    for _ in range(5):
        random_id = "".join(random.choice("0123456789abcdef") for _ in range(32))
        formatted_uuid = f"{random_id[:8]}-{random_id[8:12]}-{random_id[12:16]}-{random_id[16:20]}-{random_id[20:]}"

        test_endpoints = [
            f"/bookings/user/{formatted_uuid}/",
            f"/payments/transactions/user/{formatted_uuid}/",
        ]

        for endpoint in test_endpoints:
            response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)

            # 200 OK for another user's data would be problematic
            if response.status_code == 200:
                add_issue(
                    "high",
                    endpoint,
                    "User data leakage possible",
                    f"User can access other users' data through {endpoint}",
                    "Implement user ID validation in all user-specific endpoints",
                )


def test_input_validation():
    """Test input validation vulnerabilities"""
    print("Testing input validation...")

    # Get a valid token first
    token = login(TEST_USER_PHONE, TEST_USER_PASSWORD)
    if not token:
        print("Failed to log in, skipping input validation tests")
        return

    headers = {"Authorization": f"Token {token}"}

    # Test SQL injection in query parameters
    sql_injection_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT username, password FROM users --",
    ]

    test_endpoints = ["/services/search/", "/shops/search/", "/specialists/search/"]

    for endpoint in test_endpoints:
        for payload in sql_injection_payloads:
            response = requests.get(
                f"{API_BASE_URL}{endpoint}?q={payload}", headers=headers
            )

            # Look for signs of SQL error leakage in response
            if (
                "SQL syntax" in response.text
                or "ORA-" in response.text
                or "syntax error" in response.text
            ):
                add_issue(
                    "critical",
                    endpoint,
                    "Potential SQL injection vulnerability",
                    f"Endpoint {endpoint} showed SQL error with payload: {payload}",
                    "Use parameterized queries or ORM methods for all database operations",
                )

    # Test XSS in form/JSON inputs
    xss_payloads = [
        "<script>alert('XSS')</script>",
        'javascript:alert("XSS")',
        '<img src="x" onerror="alert(\'XSS\')">',
    ]

    data_endpoints = [
        ("/users/profile/", "PATCH", {"name": None}),
        ("/bookings/", "POST", {"notes": None}),
        ("/payments/methods/", "POST", {"name": None}),
    ]

    for endpoint, method, data_template in data_endpoints:
        for payload in xss_payloads:
            data = data_template.copy()
            for key in data:
                data[key] = payload

            if method == "POST":
                response = requests.post(
                    f"{API_BASE_URL}{endpoint}", json=data, headers=headers
                )
            elif method == "PATCH":
                response = requests.patch(
                    f"{API_BASE_URL}{endpoint}", json=data, headers=headers
                )

            if response.status_code < 400:
                # Check if we can retrieve the saved XSS payload
                if method == "PATCH" and endpoint == "/users/profile/":
                    check_response = requests.get(
                        f"{API_BASE_URL}/users/profile/", headers=headers
                    )
                    if payload in check_response.text:
                        add_issue(
                            "high",
                            endpoint,
                            "Stored XSS vulnerability",
                            f"Endpoint {endpoint} accepted and stored XSS payload: {payload}",
                            "Implement proper input sanitization for all user inputs",
                        )


def test_rate_limiting():
    """Test for rate limiting protections"""
    print("Testing rate limiting...")

    # Test login endpoint rate limiting
    login_attempts = 20
    successful = 0

    for i in range(login_attempts):
        # Use invalid credentials to avoid actual login
        response = requests.post(
            f"{API_BASE_URL}/auth/login/",
            json={
                "phone_number": f"+966{random.randint(500000000, 599999999)}",
                "password": "WrongPassword123",
            },
        )

        if response.status_code != 429:  # 429 is Too Many Requests
            successful += 1

        # Small pause to avoid overwhelming the server
        time.sleep(0.2)

    # If more than 10 attempts succeed without rate limiting, flag it
    if successful > 10:
        add_issue(
            "high",
            "/auth/login/",
            "Insufficient rate limiting on login",
            f"Made {successful} out of {login_attempts} failed login attempts without being rate limited",
            "Implement strict rate limiting on authentication endpoints to prevent brute force attacks",
        )

    # Test SMS verification endpoint rate limiting
    verification_attempts = 10
    successful_verify = 0

    for i in range(verification_attempts):
        response = requests.post(
            f"{API_BASE_URL}/auth/request-otp/",
            json={"phone_number": f"+966{random.randint(500000000, 599999999)}"},
        )

        if response.status_code != 429:
            successful_verify += 1

        time.sleep(0.2)

    if successful_verify > 5:
        add_issue(
            "high",
            "/auth/request-otp/",
            "Insufficient rate limiting on OTP requests",
            f"Made {successful_verify} out of {verification_attempts} OTP requests without being rate limited",
            "Implement strict rate limiting on OTP verification endpoints to prevent abuse",
        )


def test_csrf_protections(token):
    """Test CSRF protections on non-API endpoints"""
    print("Testing CSRF protections...")

    if not token:
        print("Failed to log in, skipping CSRF tests")
        return

    # Test session-based Django views that should require CSRF tokens
    headers = {
        "Authorization": f"Token {token}",
        "Cookie": f"sessionid=test_session; csrftoken=invalid_token",
        "Referer": API_BASE_URL,
    }

    # Try accessing session-based endpoints without valid CSRF
    for endpoint in ["/admin/", "/accounts/profile/", "/dashboard/"]:
        response = requests.post(
            f"{API_BASE_URL.replace('/api/v1', '')}{endpoint}",
            data={"test": "data"},
            headers=headers,
        )

        if response.status_code != 403:  # Should be Forbidden due to CSRF
            add_issue(
                "high",
                endpoint,
                "Missing CSRF protection",
                f"Endpoint {endpoint} accepted POST request without valid CSRF token",
                "Ensure Django's CSRF middleware is properly configured for all views",
            )


def test_sensitive_data_exposure():
    """Test for sensitive data exposure"""
    print("Testing sensitive data exposure...")

    token = login(TEST_USER_PHONE, TEST_USER_PASSWORD)
    if not token:
        print("Failed to log in, skipping sensitive data exposure tests")
        return

    headers = {"Authorization": f"Token {token}"}

    # Check if debugging information is exposed in error responses
    endpoints_to_test = [
        "/bookings/999999999/",
        "/payments/transactions/invalid-id/",
        "/services/9999999999/",
    ]

    for endpoint in endpoints_to_test:
        response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)

        # Look for signs of detailed error exposure
        response_body = response.text.lower()
        sensitive_indicators = [
            "traceback",
            "error at line",
            "stack trace",
            "debug",
            "django.db",
            "postgresql",
            "mysql",
            "exception in",
            'file "/',
            "django/core",
        ]

        for indicator in sensitive_indicators:
            if indicator in response_body:
                add_issue(
                    "high",
                    endpoint,
                    "Sensitive error details exposed",
                    f"Endpoint {endpoint} is exposing detailed error information: '{indicator}'",
                    "Configure DEBUG=False in production and implement proper error handling",
                )
                break

    # Test if payment information is exposed in responses
    payment_endpoints = ["/payments/history/", "/payments/methods/"]

    sensitive_payment_fields = [
        "cvv",
        "cvc",
        "card_security_code",
        "security_code",
        "card_number",
        "full_card_number",
    ]

    for endpoint in payment_endpoints:
        response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)

        if response.status_code == 200:
            try:
                data = response.json()

                # Walk through nested JSON looking for sensitive fields
                found_sensitive = []
                stack = [([], data)]

                while stack:
                    path, current = stack.pop()

                    if isinstance(current, dict):
                        for key, value in current.items():
                            if key.lower() in sensitive_payment_fields and value:
                                found_sensitive.append(f"{'.'.join(path)}.{key}")

                            if isinstance(value, (dict, list)):
                                stack.append((path + [key], value))

                    elif isinstance(current, list):
                        for i, item in enumerate(current):
                            if isinstance(item, (dict, list)):
                                stack.append((path + [str(i)], item))

                if found_sensitive:
                    add_issue(
                        "critical",
                        endpoint,
                        "Sensitive payment data exposed",
                        f"Endpoint {endpoint} is exposing sensitive payment data fields: {', '.join(found_sensitive)}",
                        "Never return full payment details in API responses",
                    )

            except ValueError:
                # Not JSON response
                pass


def run_security_tests():
    """Run all API security tests"""
    print("=== Starting QueueMe API Security Tests ===\n")

    # Get tokens for testing
    user_token = login(TEST_USER_PHONE, TEST_USER_PASSWORD)
    admin_token = login(ADMIN_USER_PHONE, ADMIN_USER_PASSWORD)

    # Run tests
    test_authentication_bypasses()
    if user_token and admin_token:
        test_authorization_bypasses(user_token, admin_token)
    else:
        print("Skipping authorization tests due to login failure")

    test_input_validation()
    test_rate_limiting()
    if user_token:
        test_csrf_protections(user_token)
    else:
        print("Skipping CSRF tests due to login failure")

    test_sensitive_data_exposure()

    # Generate report
    print("\n\n=== API SECURITY TEST REPORT ===\n")

    if not security_issues:
        print("No security issues found! 🎉")
    else:
        print(f"Found {len(security_issues)} security issues:\n")

        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}

        for issue in security_issues:
            by_severity[issue["severity"]].append(issue)

        for severity in ["critical", "high", "medium", "low"]:
            issues = by_severity[severity]
            if issues:
                print(f"\n{severity.upper()} SEVERITY ISSUES ({len(issues)}):")
                for i, issue in enumerate(issues, 1):
                    print(f"\n{i}. {issue['title']} at {issue['endpoint']}")
                    print(f"   Details: {issue['details']}")
                    print(f"   Recommendation: {issue['recommendation']}")

    # Save report to file
    with open("api_security_report.json", "w") as f:
        json.dump(security_issues, f, indent=2)

    print(f"\nAPI security test report saved to api_security_report.json")


if __name__ == "__main__":
    run_security_tests()
