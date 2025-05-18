# QueueMe Security Audit Tools

This directory contains security audit tools for the QueueMe application designed to identify potential vulnerabilities in authentication, payment processing, and API endpoints.

## Prerequisites

- Python 3.8+
- Django
- Safety package (`pip install safety`)
- Requests package (`pip install requests`)

## Available Tools

1. **General Security Audit**: Analyzes Django security settings, models, database connections, and dependencies.
2. **API Security Tests**: Checks for common API vulnerabilities like authentication bypasses, authorization issues, and input validation problems.

## Running the Audit Tools

### General Security Audit

This tool checks Django-specific security settings and security-critical components:

```bash
# Navigate to project root
cd /path/to/queueme

# Set environment variables
export DJANGO_SETTINGS_MODULE=queueme.settings

# Run the audit
python security/security_audit.py
```

The script will generate a comprehensive report identifying security issues with severity ratings.

### API Security Tests

This tool tests the API endpoints for common security vulnerabilities:

```bash
# Set up environment variables
export API_BASE_URL="https://your-queueme-instance.com/api/v1" # Change to your API URL
export TEST_USER_PHONE="+9665XXXXXXXX"  # Replace with valid user phone
export TEST_USER_PASSWORD="TestPass123!" # Replace with valid password
export ADMIN_USER_PHONE="+9665XXXXXXXX"  # Replace with admin phone
export ADMIN_USER_PASSWORD="AdminPass123!" # Replace with admin password

# Run the tests
python security/api_security_test.py
```

## Security Issues and Remediation

The audit tools categorize issues by severity:

- **Critical**: Must be fixed immediately
- **High**: Requires urgent attention
- **Medium**: Should be addressed in an upcoming sprint
- **Low**: Minor issues to fix when time permits

### Common Issues and Fixes

#### Authentication & Authorization
- Enable HTTPS redirection with `SECURE_SSL_REDIRECT = True`
- Set secure cookie flags with `SESSION_COOKIE_SECURE = True`
- Implement proper account lockout after failed login attempts
- Use PBKDF2 or Argon2 for password hashing

#### Payment Security
- Use idempotency keys for payment transactions
- Always use `DecimalField` for monetary values
- Never expose sensitive payment details in API responses
- Store payment credentials securely (never in code)

#### API Security
- Implement rate limiting on authentication endpoints
- Validate input thoroughly and use parameterized queries
- Set up proper CSRF protection for session-based views
- Configure proper error handling to avoid leaking sensitive information

## Running Automated Scans

For more thorough security testing, consider running these additional tools:

```bash
# Dependency vulnerability scanning
pip install safety && safety check -r requirements.txt

# Django security check
python manage.py check --deploy

# Static code analysis
bandit -r .
```

## Recommended Security Practices

1. Keep all dependencies up-to-date
2. Use environment variables for all sensitive configuration
3. Implement Multi-Factor Authentication (MFA) for admin accounts
4. Deploy a Web Application Firewall (WAF)
5. Regularly review and rotate API keys and credentials
6. Enable logging for security-critical operations
7. Conduct regular security audits and penetration testing
