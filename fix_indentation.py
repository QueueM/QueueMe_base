#!/usr/bin/env python3

with open("apps/notificationsapp/services/notification_service.py", "r") as file:
    lines = file.readlines()

# Locate the _check_sms_rate_limit method
start_index = 0
end_index = 0
for i, line in enumerate(lines):
    if "_check_sms_rate_limit" in line:
        start_index = i
        break

# Rewrite the method with correct indentation
sms_method = """    @classmethod
    def _check_sms_rate_limit(cls, recipient_id: str) -> bool:
        \"\"\"
        Check if SMS rate limit has been exceeded.

        Args:
            recipient_id: ID of the recipient

        Returns:
            Boolean indicating if rate limit is not exceeded
        \"\"\"
        # Check user-specific rate limit
        user_key = f"sms_rate_limit:{recipient_id}"
        user_count = cache.get(user_key, 0)

        if user_count >= SMS_RATE_LIMIT["user"]:
            return False

        # Check global rate limit
        global_key = "sms_rate_limit:global"
        global_count = cache.get(global_key, 0)

        if global_count >= SMS_RATE_LIMIT["global"]:
            return False

        # Increment counters
        cache.set(user_key, user_count + 1, 3600)  # 1 hour expiry
        cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry

        return True
"""

# Locate the _check_email_rate_limit method
email_start_index = 0
for i, line in enumerate(lines):
    if "_check_email_rate_limit" in line:
        email_start_index = i
        break

# Rewrite the method with correct indentation
email_method = """    @classmethod
    def _check_email_rate_limit(cls, recipient_id: str) -> bool:
        \"\"\"
        Check if email rate limit has been exceeded.

        Args:
            recipient_id: ID of the recipient

        Returns:
            Boolean indicating if rate limit is not exceeded
        \"\"\"
        # Check user-specific rate limit
        user_key = f"email_rate_limit:{recipient_id}"
        user_count = cache.get(user_key, 0)

        if user_count >= EMAIL_RATE_LIMIT["user"]:
            return False

        # Check global rate limit
        global_key = "email_rate_limit:global"
        global_count = cache.get(global_key, 0)

        if global_count >= EMAIL_RATE_LIMIT["global"]:
            return False

        # Increment counters
        cache.set(user_key, user_count + 1, 3600)  # 1 hour expiry
        cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry

        return True
"""

# Find the end of the first method and the start of the second
for i in range(start_index + 1, len(lines)):
    if "@classmethod" in lines[i] and "_check_email_rate_limit" in lines[i + 1]:
        end_index = i
        break

# Replace the methods with the corrected versions
new_lines = (
    lines[:start_index]
    + sms_method.splitlines(True)
    + lines[email_start_index : email_start_index + 1]
)
new_lines = new_lines + email_method.splitlines(True) + lines[email_start_index + 29 :]

with open("apps/notificationsapp/services/notification_service.py", "w") as file:
    file.writelines(new_lines)

print("Fixed indentation in notification_service.py")
