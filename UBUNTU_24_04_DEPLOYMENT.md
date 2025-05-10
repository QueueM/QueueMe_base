# QueueMe Deployment Guide for Ubuntu 24.04 LTS

This guide provides step-by-step instructions for deploying QueueMe on Ubuntu 24.04 LTS without using Docker.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-installation](#pre-installation)
3. [Automated Deployment](#automated-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Post-installation](#post-installation)
6. [SSL Configuration](#ssl-configuration)
7. [Backup and Restore](#backup-and-restore)
8. [Troubleshooting](#troubleshooting)

## System Requirements

- Ubuntu 24.04 LTS (Noble Numbat)
- At least 2GB RAM (4GB recommended)
- At least 20GB disk space
- Public IP address or domain name (for production)
- Non-root user with sudo privileges

## Pre-installation

Before proceeding with the installation, ensure your system is updated:

```bash
sudo apt update
sudo apt upgrade -y
```

## Automated Deployment

We've created a script that automates the deployment process. This is the recommended method for most users:

```bash
# Navigate to your project directory
cd /path/to/queueme

# Make the script executable if it's not already
chmod +x scripts/ubuntu_24_04_migration.sh

# Run the migration script
./scripts/ubuntu_24_04_migration.sh
```

The script will:
1. Install all required dependencies
2. Set up PostgreSQL with PostGIS
3. Configure Redis
4. Create a Python virtual environment
5. Install Python dependencies
6. Configure Nginx
7. Set up Supervisor for process management
8. Configure the firewall
9. Run Django migrations and collect static files

## Manual Deployment

If you prefer to deploy manually or need to customize the installation, follow these steps:

### 1. Install dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev postgresql postgresql-contrib postgresql-client redis-server nginx libpq-dev build-essential libssl-dev libffi-dev supervisor git curl wget gdal-bin libgdal-dev binutils libproj-dev
```

### 2. Install PostGIS extension

```bash
# Get PostgreSQL version
PG_VERSION=$(psql --version | awk '{print $3}' | cut -d'.' -f1)

# Install PostGIS
sudo apt install -y postgis postgresql-${PG_VERSION}-postgis-3
```

### 3. Set up PostgreSQL

```bash
# Create database user
sudo -u postgres psql -c "CREATE USER queueme WITH PASSWORD 'queueme' CREATEDB;"

# Create database
sudo -u postgres psql -c "CREATE DATABASE queueme WITH OWNER queueme;"

# Enable PostGIS extension
sudo -u postgres psql -d queueme -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Restart PostgreSQL
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

### 4. Configure Redis

```bash
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### 5. Set up Python environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install wheel setuptools
pip install -r requirements.txt
```

### 6. Set up environment variables

```bash
# Copy the example .env file
cp .env.example .env

# Edit the .env file with your configuration
nano .env
```

### 7. Configure Nginx

Create a new Nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/queueme
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;  # Replace with your domain or IP

    client_max_body_size 100M;
    
    location /static/ {
        alias /path/to/queueme/staticfiles/;
    }
    
    location /media/ {
        alias /path/to/queueme/media/;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the configuration:

```bash
sudo ln -sf /etc/nginx/sites-available/queueme /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 8. Configure Supervisor

Create a new Supervisor configuration file:

```bash
sudo nano /etc/supervisor/conf.d/queueme.conf
```

Add the following configuration:

```ini
[program:queueme_gunicorn]
command=/path/to/queueme/venv/bin/gunicorn queueme.wsgi:application --workers 4 --bind 127.0.0.1:8000
directory=/path/to/queueme
user=your_username
autostart=true
autorestart=true
stdout_logfile=/path/to/queueme/logs/gunicorn_out.log
stderr_logfile=/path/to/queueme/logs/gunicorn_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_daphne]
command=/path/to/queueme/venv/bin/daphne -b 127.0.0.1 -p 8001 queueme.asgi:application
directory=/path/to/queueme
user=your_username
autostart=true
autorestart=true
stdout_logfile=/path/to/queueme/logs/daphne_out.log
stderr_logfile=/path/to/queueme/logs/daphne_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_celery]
command=/path/to/queueme/venv/bin/celery -A queueme worker --loglevel=info
directory=/path/to/queueme
user=your_username
autostart=true
autorestart=true
stdout_logfile=/path/to/queueme/logs/celery_out.log
stderr_logfile=/path/to/queueme/logs/celery_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_celery_beat]
command=/path/to/queueme/venv/bin/celery -A queueme beat --loglevel=info
directory=/path/to/queueme
user=your_username
autostart=true
autorestart=true
stdout_logfile=/path/to/queueme/logs/celery_beat_out.log
stderr_logfile=/path/to/queueme/logs/celery_beat_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"
```

Update Supervisor:

```bash
sudo supervisorctl reread
sudo supervisorctl update
```

### 9. Configure Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable
```

### 10. Run Django migrations and collect static files

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=queueme.settings.production
python manage.py check
python manage.py collectstatic --noinput
python manage.py migrate
```

## Post-installation

After completing the installation, follow these post-installation steps:

### 1. Create a superuser

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=queueme.settings.production
python manage.py createsuperuser
```

### 2. Test the application

Visit your server's IP address or domain name in a web browser to verify that the application is running correctly.

### 3. Set up proper file permissions

```bash
# Make sure the media and static directories are writable
sudo chown -R www-data:www-data media staticfiles
```

## SSL Configuration

For production environments, it's highly recommended to set up SSL using Let's Encrypt:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your_domain.com -d www.your_domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## Backup and Restore

### Backup

```bash
# Create backup directory
mkdir -p backups

# Backup PostgreSQL database
pg_dump -U queueme queueme > backups/queueme_db_$(date +%Y-%m-%d).sql

# Backup media files
tar -czf backups/queueme_media_$(date +%Y-%m-%d).tar.gz media/

# Backup environment configuration
cp .env backups/.env.$(date +%Y-%m-%d)
```

### Restore

```bash
# Restore PostgreSQL database
psql -U queueme queueme < backups/queueme_db_YYYY-MM-DD.sql

# Restore media files
tar -xzf backups/queueme_media_YYYY-MM-DD.tar.gz

# Restore environment configuration
cp backups/.env.YYYY-MM-DD .env
```

## Troubleshooting

### Checking logs

```bash
# Check Django logs
tail -f logs/queueme.log

# Check Gunicorn logs
tail -f logs/gunicorn_out.log logs/gunicorn_err.log

# Check Daphne logs
tail -f logs/daphne_out.log logs/daphne_err.log

# Check Celery logs
tail -f logs/celery_out.log logs/celery_err.log

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

### Common issues

1. **Database connection issues**: Ensure PostgreSQL is running and the database credentials in your `.env` file are correct.

2. **Static files not found**: Run `python manage.py collectstatic` and ensure the Nginx configuration points to the correct static files directory.

3. **Permission errors**: Ensure the application files are owned by the correct user and have the correct permissions.

4. **500 Internal Server Error**: Check the Nginx and Gunicorn logs for specific error messages.

5. **502 Bad Gateway**: Ensure Gunicorn is running and configured correctly.

6. **WebSocket connection errors**: Ensure Daphne is running and the Nginx WebSocket configuration is correct.

For additional help, consult the Django documentation or open an issue in the QueueMe repository. 