# QueueMe Deployment Documentation

## Server Information
- Server: Ubuntu 24.04 LTS
- IP: 148.72.244.135
- Domains: queueme.net, shop.queueme.net, admin.queueme.net, api.queueme.net

## Services
- Django application: queueme.service
- WebSockets: queueme-daphne.service
- Task queue: queueme-celery.service 
- Scheduled tasks: queueme-celery-beat.service

## Maintenance
- Database backups run daily at 2 AM in /home/arise/db_backups
- Log rotation configured for all application logs
- SSL certificates auto-renew via cron
- System updates configured with unattended-upgrades

## Deployment Process
Run /home/arise/deploy.sh to update the application from GitHub
