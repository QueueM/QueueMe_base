#!/usr/bin/env python
"""
Test script for the audit logging system.
This script will add some sample log entries to the audit_log.db.
"""

import datetime
import os
import random
import sys
import time
import uuid

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Import our audit logging module
    from utils.admin.audit_db import get_audit_logs, get_audit_stats, log_admin_action

    # Sample user IDs
    USERS = ["1", "2", "3", "4", "5"]

    # Sample action types
    ACTIONS = ["create", "update", "delete", "view", "login", "logout", "approve", "reject"]

    # Sample targets
    TARGETS = ["User", "Shop", "Booking", "Service", "Payment", "Category", "Role"]

    def generate_sample_logs(count=50):
        """Generate some sample audit logs"""
        print(f"Generating {count} sample audit logs...")

        for i in range(count):
            # Random user
            user_id = random.choice(USERS)

            # Random action
            action_type = random.choice(ACTIONS)

            # Random target
            target_model = random.choice(TARGETS)

            # Random ID
            target_id = str(random.randint(1, 100))

            # Create action detail
            action_detail = f"{action_type.capitalize()} {target_model} #{target_id}"

            # Random IP address
            ip_address = f"192.168.1.{random.randint(1, 255)}"

            # User agent
            browser_info = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"

            # Status
            status = "success" if random.random() > 0.1 else "failure"

            # Log the action
            log_id = log_admin_action(
                user_id=user_id,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                action_detail=action_detail,
                ip_address=ip_address,
                browser_info=browser_info,
                status=status,
            )

            print(f"Created log entry {i+1}/{count}: {action_detail} (ID: {log_id})")

            # Sleep briefly so timestamps will differ
            time.sleep(0.1)

    def view_logs():
        """View some logs from the database"""
        print("\nRetrieving logs from database:")
        logs = get_audit_logs(limit=5)

        for i, log in enumerate(logs):
            print(f"{i+1}. [{log['timestamp']}] {log['action_type']} - {log['action_detail']}")

    def view_stats():
        """View statistics about the logs"""
        print("\nRetrieving audit statistics:")
        stats = get_audit_stats()

        print(f"Total logs: {stats['total_count']}")
        print("Actions breakdown:")
        for action, count in stats["action_counts"].items():
            print(f"  {action}: {count}")

        print("Daily counts:")
        for day, count in stats["daily_counts"].items():
            print(f"  {day}: {count}")

    def main():
        """Main function"""
        # Check if we should generate new logs
        if len(sys.argv) > 1 and sys.argv[1] == "generate":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            generate_sample_logs(count)

        # Display some logs
        view_logs()

        # Display statistics
        view_stats()

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this script from the project root directory.")
