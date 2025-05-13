#!/usr/bin/env python
"""
Security audit script for QueueMe authentication and payment systems.
This script checks for common security vulnerabilities and misconfigurations.
"""

import json
import os
import re
import sys

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")

import django  # noqa: E402

django.setup()

import requests  # noqa: E402
from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.core.exceptions import ImproperlyConfigured  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connections  # noqa: E402
from django.middleware.security import SecurityMiddleware  # noqa: E402

# Results storage
security_issues = {"critical": [], "high": [], "medium": [], "low": [], "info": []}


def add_issue(severity, system, title, details, recommendation):
    """Add a security issue to the results"""
    security_issues[severity].append(
        {
            "system": system,
            "title": title,
            "details": details,
            "recommendation": recommendation,
        }
    )


def check_django_security_settings():
    """Check Django security settings"""
    print("Checking Django security settings...")

    # Check HTTPS settings
    if not settings.SECURE_SSL_REDIRECT:
        add_issue(
            "high",
            "authentication",
            "SECURE_SSL_REDIRECT is disabled",
            "Your site is not configured to redirect HTTP traffic to HTTPS",
            "Enable SECURE_SSL_REDIRECT in settings.py",
        )

    # Check session cookie settings
    if not settings.SESSION_COOKIE_SECURE:
        add_issue(
            "high",
            "authentication",
            "SESSION_COOKIE_SECURE is disabled",
            "Your session cookies are not set with the 'secure' flag",
            "Enable SESSION_COOKIE_SECURE in settings.py",
        )

    # Check CSRF cookie settings
    if not settings.CSRF_COOKIE_SECURE:
        add_issue(
            "high",
            "authentication",
            "CSRF_COOKIE_SECURE is disabled",
            "Your CSRF cookies are not set with the 'secure' flag",
            "Enable CSRF_COOKIE_SECURE in settings.py",
        )

    # Check HSTS settings
    if not settings.SECURE_HSTS_SECONDS:
        add_issue(
            "medium",
            "authentication",
            "SECURE_HSTS_SECONDS is not set",
            "HTTP Strict Transport Security (HSTS) is not enabled",
            "Set SECURE_HSTS_SECONDS to at least 31536000 (1 year)",
        )
    elif settings.SECURE_HSTS_SECONDS < 31536000:
        add_issue(
            "low",
            "authentication",
            "SECURE_HSTS_SECONDS is too low",
            f"HSTS is set to {settings.SECURE_HSTS_SECONDS} seconds, which is less than recommended",
            "Set SECURE_HSTS_SECONDS to at least 31536000 (1 year)",
        )

    # Check content type nosniff
    if not settings.SECURE_CONTENT_TYPE_NOSNIFF:
        add_issue(
            "medium",
            "authentication",
            "SECURE_CONTENT_TYPE_NOSNIFF is disabled",
            "Content type sniffing protection is not enabled",
            "Enable SECURE_CONTENT_TYPE_NOSNIFF in settings.py",
        )

    # Check XSS filter
    if not getattr(settings, "SECURE_BROWSER_XSS_FILTER", False):
        add_issue(
            "medium",
            "authentication",
            "SECURE_BROWSER_XSS_FILTER is disabled",
            "XSS browser protection is not enabled",
            "Enable SECURE_BROWSER_XSS_FILTER in settings.py",
        )

    # Check X-Frame-Options
    if not getattr(settings, "X_FRAME_OPTIONS", None) or settings.X_FRAME_OPTIONS == "ALLOW":
        add_issue(
            "medium",
            "authentication",
            "X_FRAME_OPTIONS is not properly set",
            "Your site is potentially vulnerable to clickjacking attacks",
            "Set X_FRAME_OPTIONS to 'DENY' or 'SAMEORIGIN' in settings.py",
        )

    # Check SECRET_KEY strength
    secret_key = settings.SECRET_KEY
    if len(secret_key) < 50:
        add_issue(
            "high",
            "authentication",
            "SECRET_KEY is too short",
            f"Your SECRET_KEY is only {len(secret_key)} characters long",
            "Generate a new, longer SECRET_KEY with at least 50 characters",
        )

    # Check for hardcoded secrets
    settings_files = [
        os.path.join(settings.BASE_DIR, "queueme/settings/base.py"),
        os.path.join(settings.BASE_DIR, "queueme/settings/development.py"),
        os.path.join(settings.BASE_DIR, "queueme/settings/production.py"),
    ]

    for settings_file in settings_files:
        if os.path.exists(settings_file):
            try:
                with open(settings_file) as f:
                    content = f.read()
                    if "SECRET_KEY" in content and any(secret in content for secret in ["'", '"']):
                        add_issue(
                            "critical",
                            "authentication",
                            f"SECRET_KEY might be hardcoded in {os.path.basename(settings_file)}",
                            f"Your SECRET_KEY might be hardcoded in {os.path.basename(settings_file)}",
                            "Move SECRET_KEY to an environment variable or .env file",
                        )
            except Exception as e:
                print(f"Warning: Could not check {settings_file}: {e}")


def check_authentication_models():
    """Check authentication models for security issues"""
    print("Checking authentication models...")

    try:
        User = apps.get_model("authapp", "User")

        # Check password hashing algorithm
        # Fetch one user (just for checking hash format)
        user = User.objects.first()
        if user:
            password_hash = user.password
            if not password_hash.startswith(("pbkdf2_sha256", "bcrypt", "argon2")):
                add_issue(
                    "critical",
                    "authentication",
                    "Weak password hashing algorithm",
                    f"Your application is using {password_hash.split('$')[0]} for password hashing, which is not secure",
                    "Configure Django to use PBKDF2, Argon2, or BCrypt for password hashing",
                )

        # Check login attempt throttling
        login_attempt_exists = False
        try:
            LoginAttempt = apps.get_model("authapp", "LoginAttempt")
            login_attempt_exists = True
        except LookupError:
            add_issue(
                "high",
                "authentication",
                "No login attempt throttling found",
                "Your application does not track failed login attempts to prevent brute force attacks",
                "Implement login attempt tracking and account lockout after multiple failed attempts",
            )

        # Check password reset token model
        password_reset_exists = False
        try:
            PasswordResetToken = apps.get_model("authapp", "PasswordResetToken")
            password_reset_exists = True

            # Check if tokens expire
            if not hasattr(PasswordResetToken, "expires_at"):
                add_issue(
                    "high",
                    "authentication",
                    "Password reset tokens don't expire",
                    "Your password reset tokens don't have an expiration time",
                    "Add an expires_at field to PasswordResetToken model and check it before use",
                )
        except LookupError:
            add_issue(
                "medium",
                "authentication",
                "No dedicated password reset token model",
                "Your application may not have a secure mechanism for password resets",
                "Implement a dedicated PasswordResetToken model with proper expiration",
            )

    except LookupError:
        add_issue(
            "info",
            "authentication",
            "Could not analyze authentication models",
            "Unable to locate authentication models for analysis",
            "Ensure your User model is properly configured",
        )


def check_payment_security():
    """Check payment system security"""
    print("Checking payment system security...")

    # Check if payment models exist
    try:
        PaymentTransaction = apps.get_model("payment", "PaymentTransaction")

        # Check for idempotency key usage
        if not hasattr(PaymentTransaction, "idempotency_key"):
            add_issue(
                "high",
                "payment",
                "No idempotency key in payment transactions",
                "Your payment system does not use idempotency keys, which could lead to duplicate charges",
                "Add an idempotency_key field to PaymentTransaction model and check it before processing",
            )

        # Check for decimal usage in monetary fields
        amount_field = PaymentTransaction._meta.get_field("amount")
        if amount_field.get_internal_type() != "DecimalField":
            add_issue(
                "critical",
                "payment",
                "Non-decimal field used for monetary values",
                "Your payment system uses non-decimal fields for monetary values, which can lead to rounding errors",
                "Use DecimalField for all monetary values",
            )

        # Check for external_id field
        if not hasattr(PaymentTransaction, "external_id"):
            add_issue(
                "medium",
                "payment",
                "No external payment ID tracking",
                "Your payment system does not track external payment gateway IDs",
                "Add an external_id field to link transactions with payment provider records",
            )

    except LookupError:
        add_issue(
            "info",
            "payment",
            "Could not analyze payment models",
            "Unable to locate payment models for analysis",
            "Ensure your payment models are properly configured",
        )

    # Check Moyasar configuration
    if not hasattr(settings, "MOYASAR_API_KEY"):
        add_issue(
            "high",
            "payment",
            "Missing Moyasar API configuration",
            "Your application does not have Moyasar payment gateway configured",
            "Add MOYASAR_API_KEY to your settings",
        )
    elif getattr(settings, "MOYASAR_API_KEY", "").startswith("sk_"):
        # Check if API key is in settings file
        settings_files = [
            os.path.join(settings.BASE_DIR, "queueme/settings/base.py"),
            os.path.join(settings.BASE_DIR, "queueme/settings/development.py"),
            os.path.join(settings.BASE_DIR, "queueme/settings/production.py"),
            os.path.join(settings.BASE_DIR, "queueme/settings/moyasar.py"),
        ]

        for settings_file in settings_files:
            if os.path.exists(settings_file):
                try:
                    with open(settings_file) as f:
                        content = f.read()
                        if "MOYASAR_API_KEY" in content and "sk_" in content:
                            add_issue(
                                "critical",
                                "payment",
                                f"Moyasar API key hardcoded in {os.path.basename(settings_file)}",
                                f"Your Moyasar API key is hardcoded in {os.path.basename(settings_file)}",
                                "Move MOYASAR_API_KEY to an environment variable or .env file",
                            )
                except Exception as e:
                    print(f"Warning: Could not check {settings_file}: {e}")

    # Check webhook verification
    try:
        from apps.payment.services.payment_service import PaymentService

        if not hasattr(PaymentService, "verify_webhook_signature"):
            add_issue(
                "high",
                "payment",
                "No webhook signature verification",
                "Your payment service does not verify webhook signatures",
                "Implement webhook signature verification to prevent spoofing",
            )
    except ImportError:
        add_issue(
            "medium",
            "payment",
            "Could not analyze payment service",
            "Unable to locate payment service for webhook security analysis",
            "Implement webhook signature verification in your payment service",
        )


def check_database_connection_security():
    """Check database connection security"""
    print("Checking database connection security...")

    # Check SSL usage for PostgreSQL
    for conn_name, conn in connections.databases.items():
        if conn.get("ENGINE") == "django.db.backends.postgresql":
            if not conn.get("OPTIONS", {}).get("sslmode"):
                add_issue(
                    "high",
                    "database",
                    "Database connection not using SSL",
                    f"Your {conn_name} database connection does not enforce SSL",
                    "Set sslmode=require in your database OPTIONS",
                )


def check_dependency_vulnerabilities():
    """Check for known vulnerabilities in dependencies"""
    print("Checking for vulnerable dependencies...")

    try:
        import json
        import subprocess

        if os.path.exists("requirements.txt"):
            try:
                # First try the JSON format for programmatic processing
                try:
                    result = subprocess.run(
                        ["safety", "check", "-r", "requirements.txt", "--json"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    try:
                        safety_data = json.loads(result.stdout)
                        vulnerabilities = safety_data.get("vulnerabilities", [])

                        for vuln in vulnerabilities:
                            package_name = vuln.get("package_name")
                            vulnerable_version = vuln.get("vulnerable_version")
                            advisory = vuln.get("advisory")
                            fixed_version = vuln.get("fixed_version") or "Latest version"

                            add_issue(
                                "high",
                                "dependencies",
                                f"Vulnerable package: {package_name}",
                                f"Version {vulnerable_version} has known vulnerability: {advisory}",
                                f"Upgrade to a safe version: {fixed_version}",
                            )

                        if not vulnerabilities:
                            print("No vulnerable packages found.")

                    except json.JSONDecodeError:
                        # If JSON parsing fails, run the standard output version
                        raise subprocess.CalledProcessError(1, [], "JSON parsing failed")

                except subprocess.CalledProcessError:
                    # Run the standard output version that's more human-readable
                    plain_result = subprocess.run(
                        ["safety", "check", "-r", "requirements.txt"],
                        capture_output=True,
                        text=True,
                    )

                    # Process the plain text output
                    output_lines = plain_result.stdout.split("\n")
                    vulnerabilities_found = False

                    for line in output_lines:
                        if "Vulnerability found in" in line:
                            vulnerabilities_found = True
                            package_info = line.split("Vulnerability found in")[1].strip()
                            add_issue(
                                "high",
                                "dependencies",
                                f"Vulnerable package: {package_info}",
                                "Run 'safety check -r requirements.txt' for details",
                                "Upgrade the affected package to a non-vulnerable version",
                            )

                    if vulnerabilities_found:
                        print(
                            "Found vulnerabilities in dependencies. See security_audit_report.json for details."
                        )

                        # Save detailed output to a separate file for reference
                        vuln_report_path = os.path.join(
                            settings.BASE_DIR, "dependency_vulnerabilities.txt"
                        )
                        with open(vuln_report_path, "w") as f:
                            f.write(plain_result.stdout)
                        print(f"Detailed vulnerability report saved to {vuln_report_path}")
                    else:
                        print("No vulnerable packages found or error reading results.")

            except Exception as e:
                add_issue(
                    "info",
                    "dependencies",
                    "Error running safety check",
                    f"Error: {str(e)}",
                    "Manually run 'safety check -r requirements.txt' to check for vulnerabilities",
                )
        else:
            add_issue(
                "info",
                "dependencies",
                "Cannot check for vulnerable dependencies",
                "requirements.txt not found",
                "Ensure you have a requirements.txt file and run 'pip install safety' to check vulnerabilities",
            )
    except ImportError:
        add_issue(
            "info",
            "dependencies",
            "Cannot check for vulnerable dependencies",
            "safety package not installed",
            "Install the safety package with 'pip install safety'",
        )


def run_security_audit():
    """Run all security checks and generate report"""
    print("Starting QueueMe security audit...")

    check_django_security_settings()
    check_authentication_models()
    check_payment_security()
    check_database_connection_security()
    check_dependency_vulnerabilities()

    # Generate report
    print("\n\n======= SECURITY AUDIT REPORT =======\n")

    total_issues = sum(len(issues) for issues in security_issues.values())
    print(f"Found {total_issues} security issues:\n")

    for severity in ["critical", "high", "medium", "low", "info"]:
        issues = security_issues[severity]
        if issues:
            print(f"\n{severity.upper()} SEVERITY ISSUES ({len(issues)}):")
            for i, issue in enumerate(issues, 1):
                print(f"\n{i}. [{issue['system']}] {issue['title']}")
                print(f"   Details: {issue['details']}")
                print(f"   Recommendation: {issue['recommendation']}")

    # Save report to file
    report_path = os.path.join(settings.BASE_DIR, "security_audit_report.json")
    with open(report_path, "w") as f:
        json.dump(security_issues, f, indent=2)

    print(f"\nSecurity audit report saved to {report_path}")


if __name__ == "__main__":
    run_security_audit()
