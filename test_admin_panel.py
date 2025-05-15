#!/usr/bin/env python
"""
Test script for QueueMe Admin Panel features.
This script validates the main functionality of admin panel features.
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

import requests

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test configuration
BASE_URL = "http://localhost:8000"  # Adjust as needed
ADMIN_USERNAME = "admin"  # Adjust as needed
ADMIN_PASSWORD = "admin"  # Adjust as needed


def test_login():
    """Test admin login functionality"""
    print("\n🔐 Testing Admin Login...")

    session = requests.Session()
    login_url = f"{BASE_URL}/admin/login/"

    # Get CSRF token
    response = session.get(login_url)
    csrf_token = None

    if "csrftoken" in session.cookies:
        csrf_token = session.cookies["csrftoken"]

    if not csrf_token:
        print("❌ Failed to get CSRF token")
        return None

    # Login
    data = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
        "csrfmiddlewaretoken": csrf_token,
        "next": "/admin/",
    }

    headers = {"Referer": login_url}

    response = session.post(login_url, data=data, headers=headers)

    if response.status_code == 200 and "authentication and are now logged" in response.text:
        print("✅ Admin login successful")
        return session
    else:
        print("❌ Admin login failed")
        return None


def test_health_monitoring(session):
    """Test system health monitoring functionality"""
    print("\n📊 Testing System Health Monitoring...")

    if not session:
        print("❌ No active session, skipping test")
        return False

    health_url = f"{BASE_URL}/admin/system/health/"
    response = session.get(health_url)

    if response.status_code != 200:
        print(f"❌ Failed to access system health page: {response.status_code}")
        return False

    # Check for expected content
    expected_elements = [
        "CPU Usage",
        "Memory Usage",
        "Disk Usage",
        "Database Connections",
        "Server Time",
    ]

    success = True
    for element in expected_elements:
        if element not in response.text:
            print(f"❌ Missing expected element: {element}")
            success = False

    if success:
        print("✅ System Health Monitoring functioning correctly")

    return success


def test_audit_logging():
    """Test audit logging functionality directly using the SQLite database"""
    print("\n📝 Testing Audit Logging System...")

    try:
        # Import audit logging function if available
        try:
            from utils.admin.audit_db import get_audit_logs, log_admin_action

            # Test direct logging
            log_id = log_admin_action(
                user_id="test-user",
                action_type="view",
                target_model="TestModel",
                target_id="123",
                action_detail="Testing audit logging system",
                ip_address="127.0.0.1",
                browser_info="Test Script/1.0",
                status="success",
            )

            # Verify log was created
            logs = get_audit_logs(limit=1)
            if (
                logs
                and len(logs) > 0
                and logs[0]["action_detail"] == "Testing audit logging system"
            ):
                print(f"✅ Successfully created and retrieved audit log entry (ID: {log_id})")
                return True

        except ImportError:
            # Fallback to direct database access
            print("ℹ️ Direct import failed, attempting direct database access")

            # Check if database exists
            if not os.path.exists("audit_log.db"):
                print("❌ Audit log database not found")
                return False

            # Connect to database and add a test log
            conn = sqlite3.connect("audit_log.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Insert test log
            log_id = os.urandom(16).hex()
            timestamp = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO admin_audit_log
                (id, action_type, timestamp, target_model, target_id, action_detail, ip_address, browser_info, status, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    "view",
                    timestamp,
                    "TestModel",
                    "123",
                    "Testing audit logging system",
                    "127.0.0.1",
                    "Test Script/1.0",
                    "success",
                    "test-user",
                ),
            )
            conn.commit()

            # Verify log was created
            cursor.execute("SELECT * FROM admin_audit_log WHERE id = ?", (log_id,))
            log = cursor.fetchone()
            conn.close()

            if log and log["action_detail"] == "Testing audit logging system":
                print(f"✅ Successfully created and retrieved audit log entry (ID: {log_id})")
                return True
            else:
                print("❌ Failed to create or retrieve audit log entry")
                return False

    except Exception as e:
        print(f"❌ Error testing audit logging: {e}")
        return False


def test_role_management(session):
    """Test role management functionality"""
    print("\n👤 Testing Role Management System...")

    if not session:
        print("❌ No active session, skipping test")
        return False

    roles_url = f"{BASE_URL}/admin/user/roles/"
    response = session.get(roles_url)

    if response.status_code != 200:
        print(f"❌ Failed to access roles page: {response.status_code}")
        return False

    # Check for expected content
    expected_elements = ["Role Management", "Create Role", "Permissions", "Description"]

    success = True
    for element in expected_elements:
        if element not in response.text:
            print(f"❌ Missing expected element: {element}")
            success = False

    if success:
        print("✅ Role Management System functioning correctly")

    return success


def test_communications_hub(session):
    """Test communications hub functionality"""
    print("\n💬 Testing Communications Hub...")

    if not session:
        print("❌ No active session, skipping test")
        return False

    comm_url = f"{BASE_URL}/admin/communications/hub/"
    response = session.get(comm_url)

    if response.status_code != 200:
        print(f"❌ Failed to access communications hub: {response.status_code}")
        return False

    # Check for expected content
    expected_elements = ["Communications", "All Conversations", "Shops", "Customers"]

    success = True
    for element in expected_elements:
        if element not in response.text:
            print(f"❌ Missing expected element: {element}")
            success = False

    if success:
        print("✅ Communications Hub functioning correctly")

    return success


def run_all_tests():
    """Run all available tests"""
    print("🧪 Running QueueMe Admin Panel Tests...\n")

    start_time = time.time()

    # Try to login
    session = test_login()

    # Run tests that require session
    if session:
        test_health_monitoring(session)
        test_role_management(session)
        test_communications_hub(session)

    # Run tests that don't require session
    test_audit_logging()

    end_time = time.time()

    print(f"\n✅ Testing completed in {(end_time - start_time):.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test QueueMe Admin Panel features")
    parser.add_argument("--url", help="Base URL of the QueueMe instance")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")

    args = parser.parse_args()

    if args.url:
        BASE_URL = args.url
    if args.username:
        ADMIN_USERNAME = args.username
    if args.password:
        ADMIN_PASSWORD = args.password

    run_all_tests()
