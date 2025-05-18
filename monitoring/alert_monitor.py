#!/usr/bin/env python
"""
QueueMe Alert Monitor

Monitors system health and sends alerts when issues are detected.
This script is designed to be run periodically via cron or systemd timer.

Features:
1. Monitors database connectivity
2. Monitors Redis connectivity
3. Monitors Celery workers
4. Monitors disk space, CPU, and memory usage
5. Monitors application-specific metrics
6. Sends alerts via email, SMS, and in-app notifications
7. Prevents alert storms with cooldown periods
"""

import argparse
import datetime
import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# Add project to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(PROJECT_DIR, "logs", "alert_monitor.log")),
    ],
)
logger = logging.getLogger("alert_monitor")

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")

# Alert configuration
DEFAULT_ALERT_CONFIG = {
    "disk_warning_threshold": 80,  # Percentage
    "disk_critical_threshold": 90,  # Percentage
    "memory_warning_threshold": 80,  # Percentage
    "memory_critical_threshold": 90,  # Percentage
    "cpu_warning_threshold": 80,  # Percentage
    "cpu_critical_threshold": 90,  # Percentage
    "database_timeout": 5,  # Seconds
    "redis_timeout": 5,  # Seconds
    "alert_cooldown": {
        "warning": 1800,  # 30 minutes in seconds
        "critical": 300,  # 5 minutes in seconds
    },
    "recipients": {
        "admin_id": "00000000-0000-0000-0000-000000000001",  # Default admin user ID
        "admin_email": "admin@example.com",  # Fallback if notification service fails
        "admin_phone": None,  # Fallback if notification service fails
    },
}

# Path to store alert state
ALERT_STATE_FILE = os.path.join(PROJECT_DIR, "monitoring", ".alert_state.json")


def load_alert_state():
    """
    Load alert state from file

    Returns:
        Dictionary with alert state
    """
    if not os.path.exists(ALERT_STATE_FILE):
        return {"last_alerts": {}}

    try:
        with open(ALERT_STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading alert state: {str(e)}")
        return {"last_alerts": {}}


def save_alert_state(state):
    """
    Save alert state to file

    Args:
        state: Alert state dictionary
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(ALERT_STATE_FILE), exist_ok=True)

        with open(ALERT_STATE_FILE, "w") as f:
            json.dump(state, f)
    except IOError as e:
        logger.error(f"Error saving alert state: {str(e)}")


def run_health_check():
    """
    Run health check script and return results

    Returns:
        Dictionary with health check results
    """
    health_check_script = os.path.join(PROJECT_DIR, "monitoring", "health_check.py")

    try:
        result = subprocess.run(
            [sys.executable, health_check_script, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,  # Timeout after 60 seconds
        )

        if result.returncode != 0:
            logger.error(f"Health check failed with code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            return None

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        logger.error("Health check timed out")
        return None
    except json.JSONDecodeError:
        logger.error("Health check returned invalid JSON")
        logger.error(f"Output: {result.stdout}")
        return None
    except Exception as e:
        logger.error(f"Error running health check: {str(e)}")
        return None


def check_alert_cooldown(alert_id, severity, config, state):
    """
    Check if an alert is in cooldown period

    Args:
        alert_id: Identifier for the alert
        severity: Severity of the alert (warning or critical)
        config: Alert configuration
        state: Current alert state

    Returns:
        Boolean indicating if alert should be suppressed
    """
    now = datetime.datetime.now().timestamp()
    last_alerts = state.get("last_alerts", {})

    # If alert hasn't been sent before, it's not in cooldown
    if alert_id not in last_alerts:
        return False

    last_alert_time = last_alerts[alert_id].get("timestamp", 0)
    last_severity = last_alerts[alert_id].get("severity", "warning")

    # Determine cooldown period based on severity
    if severity == "critical":
        cooldown = config["alert_cooldown"].get("critical", 300)  # 5 minutes default
    else:
        cooldown = config["alert_cooldown"].get("warning", 1800)  # 30 minutes default

    # If new alert is higher severity than last, don't apply cooldown
    if severity == "critical" and last_severity == "warning":
        return False

    # Check if cooldown period has elapsed
    return (now - last_alert_time) < cooldown


def update_alert_state(alert_id, severity, state, message=None):
    """
    Update alert state after sending an alert

    Args:
        alert_id: Identifier for the alert
        severity: Severity of the alert
        state: Current alert state
        message: Alert message
    """
    now = datetime.datetime.now().timestamp()

    if "last_alerts" not in state:
        state["last_alerts"] = {}

    state["last_alerts"][alert_id] = {
        "timestamp": now,
        "severity": severity,
        "message": message,
    }

    save_alert_state(state)


def send_alert(alert_id, title, message, severity, config):
    """
    Send alert notification

    Args:
        alert_id: Identifier for the alert
        title: Alert title
        message: Alert message
        severity: Alert severity (warning or critical)
        config: Alert configuration

    Returns:
        Boolean indicating if alert was sent successfully
    """
    try:
        import django

        django.setup()

        from apps.notificationsapp.services.notification_service import NotificationService

        # Choose priority based on severity
        if severity == "critical":
            priority = "high"
        else:
            priority = "normal"

        # Send notification through the app notification service
        result = NotificationService.send_notification(
            recipient_id=config["recipients"]["admin_id"],
            notification_type="system_alert",
            title=title,
            message=message,
            channels=(
                ["email", "in_app", "sms"] if severity == "critical" else ["email", "in_app"]
            ),
            priority=priority,
            data={"alert_id": alert_id, "severity": severity},
        )

        logger.info(f"Sent alert notification for {alert_id}: {title}")
        return result.get("success", False)

    except Exception as e:
        logger.error(f"Error sending alert notification: {str(e)}")

        # Try to send email directly as fallback
        try:
            from django.conf import settings
            from django.core.mail import send_mail

            send_mail(
                subject=f"[QueueMe {severity.upper()}] {title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[config["recipients"]["admin_email"]],
            )
            logger.info(f"Sent fallback email alert for {alert_id}")
            return True
        except Exception as email_error:
            logger.error(f"Error sending fallback email: {str(email_error)}")
            return False


def process_system_alerts(health_data, config, state):
    """
    Process system alerts based on health check data

    Args:
        health_data: Health check results
        config: Alert configuration
        state: Current alert state
    """
    if not health_data or "checks" not in health_data:
        send_alert(
            alert_id="health_check_failed",
            title="Health Check Failed",
            message=f"The health check system failed to run on {socket.gethostname()}. Please check the logs.",
            severity="critical",
            config=config,
        )
        return

    # Check overall system health
    if health_data.get("summary") == "unhealthy":
        # Process individual checks to determine what's wrong
        checks = health_data.get("checks", {})

        # Check database health
        process_database_alerts(checks.get("database", {}), config, state)

        # Check Redis health
        process_redis_alerts(checks.get("redis", {}), config, state)

        # Check Celery health
        process_celery_alerts(checks.get("celery", {}), config, state)

        # Check system resources
        process_system_resource_alerts(checks.get("system", {}), config, state)

        # Check integrations
        process_integration_alerts(checks.get("integrations", {}), config, state)

        # Check application health
        process_app_alerts(checks.get("queueme_app", {}), config, state)
    else:
        # System is healthy, check for resolved alerts
        process_resolved_alerts(health_data, state, config)


def process_database_alerts(db_data, config, state):
    """
    Process database health alerts

    Args:
        db_data: Database health check data
        config: Alert configuration
        state: Current alert state
    """
    if not db_data:
        return

    if db_data.get("status") == "error":
        alert_id = "database_error"
        severity = "critical"

        if not check_alert_cooldown(alert_id, severity, config, state):
            title = "Database Connection Error"
            message = f"Database connection failed: {db_data.get('error', 'Unknown error')}"

            if send_alert(alert_id, title, message, severity, config):
                update_alert_state(alert_id, severity, state, message)

    elif db_data.get("status") == "unhealthy":
        # Check individual database connections
        for db_name, db_info in db_data.get("databases", {}).items():
            if db_info.get("status") == "error":
                alert_id = f"database_error_{db_name}"
                severity = "critical"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = f"Database {db_name} Connection Error"
                    message = f"Database {db_name} connection failed: {db_info.get('error', 'Unknown error')}"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)


def process_redis_alerts(redis_data, config, state):
    """
    Process Redis health alerts

    Args:
        redis_data: Redis health check data
        config: Alert configuration
        state: Current alert state
    """
    if not redis_data:
        return

    if redis_data.get("status") == "error":
        alert_id = "redis_error"
        severity = "critical"

        if not check_alert_cooldown(alert_id, severity, config, state):
            title = "Redis Connection Error"
            message = f"Redis connection failed: {redis_data.get('error', 'Unknown error')}"

            if send_alert(alert_id, title, message, severity, config):
                update_alert_state(alert_id, severity, state, message)

    elif redis_data.get("status") == "unhealthy":
        # Check individual Redis instances
        for redis_name, redis_info in redis_data.get("instances", {}).items():
            if redis_info.get("status") == "error":
                alert_id = f"redis_error_{redis_name}"
                severity = "critical"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = f"Redis {redis_name} Connection Error"
                    message = f"Redis {redis_name} connection failed: {redis_info.get('error', 'Unknown error')}"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)


def process_celery_alerts(celery_data, config, state):
    """
    Process Celery health alerts

    Args:
        celery_data: Celery health check data
        config: Alert configuration
        state: Current alert state
    """
    if not celery_data:
        return

    if celery_data.get("status") in ("error", "unhealthy"):
        alert_id = "celery_error"
        severity = "critical"

        if not check_alert_cooldown(alert_id, severity, config, state):
            title = "Celery Workers Error"
            message = f"Celery workers are not running properly: {celery_data.get('error', 'No workers responding')}"

            if send_alert(alert_id, title, message, severity, config):
                update_alert_state(alert_id, severity, state, message)


def process_system_resource_alerts(system_data, config, state):
    """
    Process system resource alerts

    Args:
        system_data: System resource health check data
        config: Alert configuration
        state: Current alert state
    """
    if not system_data:
        return

    if system_data.get("status") == "error":
        alert_id = "system_resource_error"
        severity = "warning"

        if not check_alert_cooldown(alert_id, severity, config, state):
            title = "System Resource Monitoring Error"
            message = (
                f"Error monitoring system resources: {system_data.get('error', 'Unknown error')}"
            )

            if send_alert(alert_id, title, message, severity, config):
                update_alert_state(alert_id, severity, state, message)

    elif system_data.get("status") == "unhealthy":
        # Check CPU usage
        if "cpu" in system_data and "usage_percent" in system_data["cpu"]:
            cpu_usage = system_data["cpu"]["usage_percent"]

            if cpu_usage >= config["cpu_critical_threshold"]:
                alert_id = "cpu_critical"
                severity = "critical"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "Critical CPU Usage"
                    message = f"CPU usage is critical: {cpu_usage}% (threshold: {config['cpu_critical_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)

            elif cpu_usage >= config["cpu_warning_threshold"]:
                alert_id = "cpu_warning"
                severity = "warning"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "High CPU Usage"
                    message = f"CPU usage is high: {cpu_usage}% (threshold: {config['cpu_warning_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)

        # Check memory usage
        if "memory" in system_data and "percent" in system_data["memory"]:
            memory_usage = system_data["memory"]["percent"]

            if memory_usage >= config["memory_critical_threshold"]:
                alert_id = "memory_critical"
                severity = "critical"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "Critical Memory Usage"
                    message = f"Memory usage is critical: {memory_usage}% (threshold: {config['memory_critical_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)

            elif memory_usage >= config["memory_warning_threshold"]:
                alert_id = "memory_warning"
                severity = "warning"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "High Memory Usage"
                    message = f"Memory usage is high: {memory_usage}% (threshold: {config['memory_warning_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)

        # Check disk usage
        if "disk" in system_data and "percent" in system_data["disk"]:
            disk_usage = system_data["disk"]["percent"]

            if disk_usage >= config["disk_critical_threshold"]:
                alert_id = "disk_critical"
                severity = "critical"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "Critical Disk Usage"
                    message = f"Disk usage is critical: {disk_usage}% (threshold: {config['disk_critical_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)

            elif disk_usage >= config["disk_warning_threshold"]:
                alert_id = "disk_warning"
                severity = "warning"

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = "High Disk Usage"
                    message = f"Disk usage is high: {disk_usage}% (threshold: {config['disk_warning_threshold']}%)"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)


def process_integration_alerts(integration_data, config, state):
    """
    Process integration health alerts

    Args:
        integration_data: Integration health check data
        config: Alert configuration
        state: Current alert state
    """
    if not integration_data:
        return

    if integration_data.get("status") == "unhealthy":
        # Check individual integrations
        for name, info in integration_data.get("integrations", {}).items():
            if info.get("status") == "error":
                alert_id = f"integration_error_{name}"
                severity = "warning"  # Integration errors are usually warning level

                if not check_alert_cooldown(alert_id, severity, config, state):
                    title = f"{name.capitalize()} Integration Error"
                    message = f"{name.capitalize()} integration failed: {info.get('error', 'Unknown error')}"

                    if send_alert(alert_id, title, message, severity, config):
                        update_alert_state(alert_id, severity, state, message)


def process_app_alerts(app_data, config, state):
    """
    Process application-specific health alerts

    Args:
        app_data: Application health check data
        config: Alert configuration
        state: Current alert state
    """
    if not app_data:
        return

    if app_data.get("status") == "error":
        alert_id = "app_error"
        severity = "warning"

        if not check_alert_cooldown(alert_id, severity, config, state):
            title = "Application Error"
            message = f"QueueMe application error: {app_data.get('error', 'Unknown error')}"

            if send_alert(alert_id, title, message, severity, config):
                update_alert_state(alert_id, severity, state, message)


def process_resolved_alerts(health_data, state, config):
    """
    Process resolved alerts

    Args:
        health_data: Health check data
        state: Current alert state
        config: Alert configuration
    """
    # Get last alerts
    last_alerts = state.get("last_alerts", {})
    resolved_alerts = []

    # Check database alerts
    db_status = health_data.get("checks", {}).get("database", {}).get("status")
    if db_status == "healthy":
        # Check if we had database alerts
        for alert_id in list(last_alerts.keys()):
            if alert_id.startswith("database_error"):
                resolved_alerts.append(alert_id)

    # Check Redis alerts
    redis_status = health_data.get("checks", {}).get("redis", {}).get("status")
    if redis_status == "healthy":
        # Check if we had Redis alerts
        for alert_id in list(last_alerts.keys()):
            if alert_id.startswith("redis_error"):
                resolved_alerts.append(alert_id)

    # Check Celery alerts
    celery_status = health_data.get("checks", {}).get("celery", {}).get("status")
    if celery_status == "healthy":
        # Check if we had Celery alerts
        for alert_id in list(last_alerts.keys()):
            if alert_id.startswith("celery_error"):
                resolved_alerts.append(alert_id)

    # Check system resource alerts
    system_status = health_data.get("checks", {}).get("system", {}).get("status")
    if system_status == "healthy":
        # Check if we had system resource alerts
        for alert_id in list(last_alerts.keys()):
            if alert_id in (
                "cpu_critical",
                "cpu_warning",
                "memory_critical",
                "memory_warning",
                "disk_critical",
                "disk_warning",
            ):
                resolved_alerts.append(alert_id)

    # Send resolved alerts
    if resolved_alerts:
        # Group alerts by type for a cleaner notification
        grouped_alerts = {}
        for alert_id in resolved_alerts:
            alert_type = alert_id.split("_")[0]
            if alert_type not in grouped_alerts:
                grouped_alerts[alert_type] = []
            grouped_alerts[alert_type].append(alert_id)

        # Send a single resolution notification per type
        for alert_type, alert_ids in grouped_alerts.items():
            title = f"{alert_type.capitalize()} Issue Resolved"
            message = f"The following {alert_type} issues have been resolved:\n"

            for alert_id in alert_ids:
                if alert_id in last_alerts:
                    alert_msg = last_alerts[alert_id].get("message", "Unknown issue")
                    message += f"- {alert_msg}\n"
                    # Remove from last_alerts
                    del last_alerts[alert_id]

            send_alert(
                alert_id=f"{alert_type}_resolved",
                title=title,
                message=message,
                severity="info",
                config=config,
            )

        # Save updated state
        save_alert_state(state)


def main():
    parser = argparse.ArgumentParser(description="QueueMe Alert Monitor")
    parser.add_argument("--config", help="Path to config file")
    args = parser.parse_args()

    # Load configuration
    config = DEFAULT_ALERT_CONFIG.copy()

    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, "r") as f:
                custom_config = json.load(f)
                # Merge configurations
                for key, value in custom_config.items():
                    if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                        config[key].update(value)
                    else:
                        config[key] = value
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading config file: {str(e)}")

    # Load alert state
    state = load_alert_state()

    # Run health check
    logger.info("Running health check")
    health_data = run_health_check()

    # Process alerts
    if health_data:
        logger.info(
            f"Processing health check results (status: {health_data.get('summary', 'unknown')})"
        )
        process_system_alerts(health_data, config, state)
    else:
        logger.error("Health check failed to return data")

        # Send error alert
        send_alert(
            alert_id="health_check_error",
            title="Health Check System Error",
            message=f"The health check system failed to return data on {socket.gethostname()}. Please check the logs.",
            severity="critical",
            config=config,
        )


if __name__ == "__main__":
    main()
