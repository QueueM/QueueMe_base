#!/usr/bin/env python3
"""
This script fixes indentation issues in the notification_service.py file.
The primary issue is with indentation of return statements in _check_sms_rate_limit
and _check_email_rate_limit methods.
"""

import re

# Path to the file
file_path = "apps/notificationsapp/services/notification_service.py"

# Read the content of the file
with open(file_path, "r") as file:
    content = file.read()

# Fix the indentation issues in _check_sms_rate_limit and _check_email_rate_limit methods
# We're looking for indented return True statements after cache.set calls
pattern1 = (
    r"cache\.set\(global_key, global_count \+ 1, 3600\)  # 1 hour expiry\n\n            return True"
)
replacement1 = (
    r"cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry\n\n        return True"
)

pattern2 = (
    r"cache\.set\(global_key, global_count \+ 1, 3600\)  # 1 hour expiry\n\n        return True"
)
replacement2 = (
    r"cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry\n\n        return True"
)

# Apply the fixes
fixed_content = re.sub(pattern1, replacement1, content)
fixed_content = re.sub(pattern2, replacement2, fixed_content)

# Write the fixed content back to the file
with open(file_path, "w") as file:
    file.write(fixed_content)

print("Fixed indentation issues in notification_service.py")
