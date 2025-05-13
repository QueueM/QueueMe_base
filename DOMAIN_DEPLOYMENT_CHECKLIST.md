# QueueMe Multi-Domain Deployment Checklist

This document outlines the steps needed to deploy QueueMe with the multi-domain configuration.

## 1. Domain Configuration

- [ ] Register all required domains:
  - queueme.net (main site)
  - www.queueme.net (redirect to main site)
  - shop.queueme.net (shop interface for businesses)
  - admin.queueme.net (admin panel)
  - api.queueme.net (API endpoints)

- [ ] Configure DNS settings to point all domains to your server IP

## 2. SSL Certificate Setup

- [ ] Install Certbot: `sudo apt-get install certbot python3-certbot-nginx`
- [ ] Obtain SSL certificates for all domains:
  ```bash
  sudo certbot --nginx -d queueme.net -d www.queueme.net
  sudo certbot --nginx -d shop.queueme.net
  sudo certbot --nginx -d admin.queueme.net
  sudo certbot --nginx -d api.queueme.net
  ```
- [ ] Verify certificate renewal: `sudo certbot renew --dry-run`

## 3. Nginx Configuration

- [ ] Install Nginx: `sudo apt-get install nginx`
- [ ] Copy the updated `queueme-nginx.conf` to `/etc/nginx/sites-available/queueme`
- [ ] Create a symbolic link: `sudo ln -s /etc/nginx/sites-available/queueme /etc/nginx/sites-enabled/`
- [ ] Test Nginx configuration: `sudo nginx -t`
- [ ] Restart Nginx: `sudo systemctl restart nginx`

## 4. Application Deployment

- [ ] Clone the QueueMe repository
- [ ] Set up a Python virtual environment:
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- [ ] Create production environment file (.env) with all required variables:
  ```
  DEBUG=False
  SECRET_KEY=your_secret_key
  DB_NAME=queueme
  DB_USER=queueme_user
  DB_PASSWORD=your_db_password
  DB_HOST=localhost
  DB_PORT=5432
  REDIS_URL=redis://localhost:6379/0
  ```
- [ ] Add Moyasar and Firebase configuration to .env:
  ```
  MOYASAR_API_KEY=your_moyasar_api_key
  MOYASAR_PUBLIC_KEY=your_moyasar_public_key
  FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
  FIREBASE_API_KEY=your_firebase_api_key
  FIREBASE_PROJECT_ID=your_project_id
  ```
- [ ] Set up static files:
  ```bash
  python manage.py collectstatic --noinput
  ```
- [ ] Run database migrations:
  ```bash
  python manage.py migrate
  ```
- [ ] Create a superuser:
  ```bash
  python manage.py createsuperuser
  ```

## 5. Gunicorn & Daphne Setup

- [ ] Install Gunicorn and Daphne:
  ```bash
  pip install gunicorn daphne
  ```

- [ ] Create systemd service for Gunicorn:
  ```bash
  sudo nano /etc/systemd/system/queueme.service
  ```

  ```ini
  [Unit]
  Description=QueueMe Gunicorn Daemon
  After=network.target

  [Service]
  User=queueme
  Group=www-data
  WorkingDirectory=/opt/queueme
  ExecStart=/opt/queueme/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 queueme.wsgi:application
  EnvironmentFile=/opt/queueme/.env
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] Create systemd service for Daphne (WebSockets):
  ```bash
  sudo nano /etc/systemd/system/queueme-daphne.service
  ```

  ```ini
  [Unit]
  Description=QueueMe Daphne Daemon
  After=network.target

  [Service]
  User=queueme
  Group=www-data
  WorkingDirectory=/opt/queueme
  ExecStart=/opt/queueme/venv/bin/daphne -b 127.0.0.1 -p 8001 queueme.asgi:application
  EnvironmentFile=/opt/queueme/.env
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] Enable and start the services:
  ```bash
  sudo systemctl enable queueme.service queueme-daphne.service
  sudo systemctl start queueme.service queueme-daphne.service
  ```

## 6. Celery Setup

- [ ] Create systemd service for Celery:
  ```bash
  sudo nano /etc/systemd/system/queueme-celery.service
  ```

  ```ini
  [Unit]
  Description=QueueMe Celery Worker
  After=network.target

  [Service]
  User=queueme
  Group=www-data
  WorkingDirectory=/opt/queueme
  ExecStart=/opt/queueme/venv/bin/celery -A queueme worker -l info
  EnvironmentFile=/opt/queueme/.env
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] Create systemd service for Celery Beat:
  ```bash
  sudo nano /etc/systemd/system/queueme-celery-beat.service
  ```

  ```ini
  [Unit]
  Description=QueueMe Celery Beat
  After=network.target

  [Service]
  User=queueme
  Group=www-data
  WorkingDirectory=/opt/queueme
  ExecStart=/opt/queueme/venv/bin/celery -A queueme beat -l info
  EnvironmentFile=/opt/queueme/.env
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] Enable and start the services:
  ```bash
  sudo systemctl enable queueme-celery.service queueme-celery-beat.service
  sudo systemctl start queueme-celery.service queueme-celery-beat.service
  ```

## 7. Verification Tests

- [ ] Test main site: https://queueme.net
- [ ] Test shop interface: https://shop.queueme.net
- [ ] Test admin panel: https://admin.queueme.net
- [ ] Test API endpoints: https://api.queueme.net/api/v1/
- [ ] Test WebSocket connections on all domains
- [ ] Test Moyasar payment integration
- [ ] Test Firebase notification sending

## 8. Monitoring Setup

- [ ] Set up log rotation:
  ```bash
  sudo nano /etc/logrotate.d/queueme
  ```

  ```
  /opt/queueme/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 queueme www-data
    sharedscripts
    postrotate
      systemctl restart queueme.service
    endscript
  }
  ```

- [ ] Set up monitoring tool (Prometheus, Grafana, etc.)
- [ ] Configure email alerts for critical errors

## 9. Backup Strategy

- [ ] Set up database backups:
  ```bash
  sudo nano /etc/cron.daily/queueme-backup
  ```

  ```bash
  #!/bin/bash
  BACKUP_DIR="/opt/backups/queueme"
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  mkdir -p $BACKUP_DIR

  # Database backup
  pg_dump -U queueme_user queueme > $BACKUP_DIR/queueme_db_$TIMESTAMP.sql

  # Media files backup
  tar -czf $BACKUP_DIR/queueme_media_$TIMESTAMP.tar.gz /opt/queueme/media

  # Keep only the last 7 backups
  find $BACKUP_DIR -name "queueme_db_*" -type f -mtime +7 -delete
  find $BACKUP_DIR -name "queueme_media_*" -type f -mtime +7 -delete
  ```

  ```bash
  chmod +x /etc/cron.daily/queueme-backup
  ```

## 10. Final Security Checks

- [ ] Set up firewall:
  ```bash
  sudo ufw allow 'Nginx Full'
  sudo ufw allow ssh
  sudo ufw enable
  ```

- [ ] Secure SSH access:
  - [ ] Disable password authentication
  - [ ] Use SSH keys only
  - [ ] Consider changing the default SSH port

- [ ] Implement rate limiting for API endpoints
- [ ] Set up fail2ban for protection against brute force attacks

## After Deployment

- [ ] Document your deployment
- [ ] Create an incidence response plan
- [ ] Set up a staging environment for future updates
