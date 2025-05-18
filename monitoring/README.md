# QueueMe Monitoring System

This directory contains tools for monitoring the QueueMe application to ensure high availability and performance in production environments.

## Components

### 1. Health Check System

The health check system (`health_check.py`) monitors critical components of the QueueMe application, including:

- Database connectivity
- Redis connectivity
- Celery workers
- External API integrations (Moyasar, Firebase, Twilio)
- System resources (CPU, memory, disk)
- Application-specific metrics

#### Usage

```bash
# Basic health check (outputs text report)
python monitoring/health_check.py

# Get JSON output
python monitoring/health_check.py --format json

# Save output to file
python monitoring/health_check.py --output health_report.txt
```

### 2. Alert System

The alert system (`alert_monitor.py`) runs periodic checks and sends notifications when issues are detected:

- Detects critical problems before they affect users
- Sends alerts through email, SMS, and in-app notifications
- Prevents alert storms with cooldown periods
- Notifies when issues are resolved

#### Usage

```bash
# Run alert monitor
python monitoring/alert_monitor.py

# Use custom configuration
python monitoring/alert_monitor.py --config monitoring/alert_config.json
```

## Setting Up Monitoring

### Configure System Monitoring

1. **Systemd Timer (Recommended for Linux)**

Create a systemd service file `/etc/systemd/system/queueme-monitor.service`:

```ini
[Unit]
Description=QueueMe Health Monitoring
After=network.target

[Service]
User=queueme
WorkingDirectory=/path/to/queueme
ExecStart=/path/to/queueme/venv/bin/python monitoring/alert_monitor.py
Environment=DJANGO_SETTINGS_MODULE=queueme.settings

[Install]
WantedBy=multi-user.target
```

Create a timer file `/etc/systemd/system/queueme-monitor.timer`:

```ini
[Unit]
Description=Run QueueMe monitoring every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
AccuracySec=1min

[Install]
WantedBy=timers.target
```

Enable and start the timer:

```bash
sudo systemctl enable queueme-monitor.timer
sudo systemctl start queueme-monitor.timer
```

2. **Cron Job (Alternative)**

Add to crontab:

```
*/5 * * * * cd /path/to/queueme && /path/to/queueme/venv/bin/python monitoring/alert_monitor.py >> /path/to/queueme/logs/cron_monitor.log 2>&1
```

### Customizing Alert Thresholds

Create a file `monitoring/alert_config.json` to customize alert thresholds:

```json
{
  "disk_warning_threshold": 80,
  "disk_critical_threshold": 90,
  "memory_warning_threshold": 80,
  "memory_critical_threshold": 90,
  "cpu_warning_threshold": 80,
  "cpu_critical_threshold": 90,
  "alert_cooldown": {
    "warning": 1800,
    "critical": 300
  },
  "recipients": {
    "admin_id": "00000000-0000-0000-0000-000000000001",
    "admin_email": "admin@example.com"
  }
}
```

## External Monitoring Integration

For comprehensive production monitoring, consider integrating with:

1. **Prometheus + Grafana**: For metrics collection and visualization
2. **Sentry**: For error tracking
3. **ELK Stack**: For centralized logging
4. **Uptime Robot**: For external uptime monitoring

Example configuration files for these integrations are provided in the `monitoring/integrations/` directory.
