# QueueMe Migration to Ubuntu 24.04 LTS

This README provides an overview of the migration process for deploying QueueMe on Ubuntu 24.04 LTS (Noble Numbat) without Docker.

## Table of Contents

1. [Migration Files](#migration-files)
2. [Migration Process](#migration-process)
3. [Post-Migration Tasks](#post-migration-tasks)
4. [Troubleshooting](#troubleshooting)
5. [Contact and Support](#contact-and-support)

## Migration Files

The following files have been prepared to assist with the migration process:

### Documentation

- **`UBUNTU_24_04_DEPLOYMENT.md`**: Comprehensive deployment guide with step-by-step instructions
- **`UBUNTU_24_04_MIGRATION_SUMMARY.md`**: High-level summary of the migration plan
- **`POSTGRESQL_SETUP.md`**: PostgreSQL setup and optimization guide
- **`REDIS_SETUP.md`**: Redis setup and optimization guide
- **`SYSTEM_REQUIREMENTS.md`**: Detailed system requirements specification

### Configuration Files

- **`ubuntu24-env-example.txt`**: Environment variables template specific to Ubuntu 24.04
- **`queueme.service`**: Systemd service file for Gunicorn (web server)
- **`queueme-daphne.service`**: Systemd service file for Daphne (WebSockets)
- **`queueme-celery.service`**: Systemd service file for Celery worker (task queue)
- **`queueme-celery-beat.service`**: Systemd service file for Celery beat (scheduled tasks)
- **`queueme-nginx.conf`**: Nginx configuration for QueueMe

### Scripts

- **`scripts/ubuntu_24_04_migration.sh`**: Automated migration script for Ubuntu 24.04
- **`scripts/verify_deployment.sh`**: Script to verify that all components are working correctly

## Migration Process

### Option 1: Automated Migration (Recommended)

1. Set up a fresh Ubuntu 24.04 LTS server
2. Clone the QueueMe repository
3. Run the automated migration script:

```bash
cd /path/to/queueme
chmod +x scripts/ubuntu_24_04_migration.sh
./scripts/ubuntu_24_04_migration.sh
```

4. Follow the on-screen instructions to complete the setup
5. Verify the deployment using the verification script:

```bash
./scripts/verify_deployment.sh
```

### Option 2: Manual Migration

For those who prefer to migrate manually or need to customize the installation:

1. Follow the detailed instructions in `UBUNTU_24_04_DEPLOYMENT.md`
2. Configure PostgreSQL using the guidance in `POSTGRESQL_SETUP.md`
3. Configure Redis using the guidance in `REDIS_SETUP.md`
4. Install and configure the systemd service files and Nginx configuration

## Post-Migration Tasks

After completing the migration, perform these tasks:

1. **Create a superuser** for the Django admin:

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=queueme.settings.production
python manage.py createsuperuser
```

2. **Set up SSL certificates** using Let's Encrypt:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

3. **Implement a backup strategy** for the database and media files
4. **Set up monitoring** to track system health and performance

## Troubleshooting

If you encounter issues during the migration:

1. Check the logs in the `logs/` directory
2. Use the verification script to identify specific problems:

```bash
./scripts/verify_deployment.sh
```

3. Review the output of individual services:

```bash
# Check Django logs
tail -f logs/queueme.log

# Check Gunicorn logs
tail -f logs/gunicorn_out.log logs/gunicorn_err.log

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log

# Check systemd service status
sudo systemctl status queueme
sudo systemctl status queueme-daphne
sudo systemctl status queueme-celery
sudo systemctl status queueme-celery-beat
```

4. Refer to the appropriate guide for component-specific troubleshooting:
   - PostgreSQL: `POSTGRESQL_SETUP.md`
   - Redis: `REDIS_SETUP.md`
   - System requirements: `SYSTEM_REQUIREMENTS.md`

## Contact and Support

If you need assistance with the migration process, please contact:

- QueueMe Support Team: support@queueme.net
- Technical Lead: tech@queueme.net
- System Administrator: sysadmin@queueme.net

---

This migration package was prepared specifically for QueueMe deployment on Ubuntu 24.04 LTS and includes all necessary configurations to ensure a smooth transition to the new operating system. 