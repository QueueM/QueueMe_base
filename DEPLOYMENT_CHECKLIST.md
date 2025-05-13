# QueueMe Deployment Checklist

This checklist provides a step-by-step guide for deploying the QueueMe platform to production environments.

## Pre-Deployment Preparation

- [ ] Run all tests to ensure everything is working correctly:
  ```bash
  python manage.py test
  ```
- [ ] Check for any code quality issues:
  ```bash
  flake8
  black --check .
  isort --check-only --profile black .
  ```
- [ ] Run security checks:
  ```bash
  bandit -r .
  ```
- [ ] Generate static files:
  ```bash
  python manage.py collectstatic --noinput
  ```
- [ ] Make sure all migrations are up to date:
  ```bash
  python manage.py makemigrations --check
  ```

## Server Setup

- [ ] Provision a server with adequate resources (recommended: 4 CPU cores, 8GB RAM, 50GB SSD)
- [ ] Install system dependencies:
  ```bash
  apt-get update
  apt-get install -y python3 python3-pip python3-venv nginx redis-server postgresql postgresql-contrib supervisor
  ```
- [ ] Create a dedicated user for running the application:
  ```bash
  adduser queueme
  usermod -aG sudo queueme
  ```
- [ ] Create application directories:
  ```bash
  mkdir -p /opt/queueme/{app,media,staticfiles,run,logs}
  chown -R queueme:queueme /opt/queueme
  ```

## Database Configuration

- [ ] Configure PostgreSQL for production:
  ```bash
  sudo -u postgres createuser queueme
  sudo -u postgres createdb queueme
  sudo -u postgres psql -c "ALTER USER queueme WITH PASSWORD 'secure_password';"
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE queueme TO queueme;"
  ```
- [ ] Enable PostGIS extension:
  ```bash
  sudo -u postgres psql -d queueme -c "CREATE EXTENSION postgis;"
  ```
- [ ] Update database settings in environment variables:
  ```
  POSTGRES_DB=queueme
  POSTGRES_USER=queueme
  POSTGRES_PASSWORD=secure_password
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
  ```

## Application Deployment

- [ ] Clone the repository:
  ```bash
  cd /opt/queueme/app
  git clone https://github.com/yourusername/queueme.git .
  ```
- [ ] Create a virtual environment:
  ```bash
  python3 -m venv /opt/queueme/venv
  source /opt/queueme/venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  ```
- [ ] Create the .env file with all required variables:
  ```bash
  cp .env.example .env
  vim .env  # Edit with proper production values
  ```
- [ ] Apply migrations:
  ```bash
  python manage.py migrate
  ```
- [ ] Create a superuser:
  ```bash
  python manage.py createsuperuser
  ```
- [ ] Collect static files:
  ```bash
  python manage.py collectstatic --noinput
  ```

## Domain Configuration

- [ ] Configure DNS records for all required domains:
  - queueme.net (main site)
  - shop.queueme.net (shop interface)
  - admin.queueme.net (admin panel)
  - api.queueme.net (API endpoints)
- [ ] Obtain SSL certificates for all domains:
  ```bash
  certbot certonly --webroot -w /var/www/html -d queueme.net -d www.queueme.net -d shop.queueme.net -d admin.queueme.net -d api.queueme.net
  ```
- [ ] Configure Nginx with the provided configuration files:
  ```bash
  cp queueme-nginx.conf /etc/nginx/sites-available/queueme
  ln -s /etc/nginx/sites-available/queueme /etc/nginx/sites-enabled/
  systemctl restart nginx
  ```

## Payment Gateway (Moyasar) Configuration

- [ ] Set up three separate wallets in Moyasar dashboard:
  - [ ] Subscription wallet for business subscription payments
  - [ ] Ads wallet for advertisement purchases
  - [ ] Merchant wallet for customer payments

- [ ] Configure API keys and webhook endpoints:
  ```
  # Subscription wallet
  MOYASAR_SUB_PUBLIC=pk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_SUB_SECRET=sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_SUB_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  MOYASAR_SUB_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/subscription/
  MOYASAR_SUB_CALLBACK_URL_COMPLETE=https://queueme.net/payments/subscription/complete

  # Ads wallet
  MOYASAR_ADS_PUBLIC=pk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_ADS_SECRET=sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_ADS_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  MOYASAR_ADS_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/ads/

  # Merchant wallet
  MOYASAR_MER_PUBLIC=pk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_MER_SECRET=sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  MOYASAR_MER_WALLET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  MOYASAR_MER_CALLBACK_URL=https://api.queueme.net/api/v1/payment/webhooks/merchant/
  ```

- [ ] Verify Moyasar configuration with the provided utility:
  ```bash
  python manage.py check_moyasar_config --test
  ```

- [ ] Ensure all webhook endpoints are correctly configured in the Moyasar dashboard for each wallet:
  - Subscription: https://api.queueme.net/api/v1/payment/webhooks/subscription/
  - Ads: https://api.queueme.net/api/v1/payment/webhooks/ads/
  - Merchant: https://api.queueme.net/api/v1/payment/webhooks/merchant/

## Service Configuration

- [ ] Configure Gunicorn for WSGI:
  ```bash
  cp config/systemd/queueme.service /etc/systemd/system/
  systemctl enable queueme
  systemctl start queueme
  ```
- [ ] Configure Daphne for ASGI/WebSockets:
  ```bash
  cp config/systemd/queueme-daphne.service /etc/systemd/system/
  systemctl enable queueme-daphne
  systemctl start queueme-daphne
  ```
- [ ] Configure Celery for background tasks:
  ```bash
  cp config/systemd/queueme-celery.service /etc/systemd/system/
  cp config/systemd/queueme-celery-beat.service /etc/systemd/system/
  systemctl enable queueme-celery queueme-celery-beat
  systemctl start queueme-celery queueme-celery-beat
  ```

## Email and SMS Configuration

- [ ] Configure email settings:
  ```
  EMAIL_HOST=smtp.provider.com
  EMAIL_PORT=587
  EMAIL_USE_TLS=True
  EMAIL_HOST_USER=your_email@provider.com
  EMAIL_HOST_PASSWORD=your_email_password
  DEFAULT_FROM_EMAIL=noreply@queueme.net
  ```
- [ ] Configure SMS settings (Twilio):
  ```
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_PHONE_NUMBER=+12345678901
  ```

## Security Configuration

- [ ] Enable security settings:
  ```
  SECURE_SSL_REDIRECT=True
  SESSION_COOKIE_SECURE=True
  CSRF_COOKIE_SECURE=True
  SECURE_HSTS_SECONDS=31536000
  SECURE_HSTS_INCLUDE_SUBDOMAINS=True
  SECURE_HSTS_PRELOAD=True
  ```
- [ ] Configure CORS settings:
  ```
  CORS_ALLOWED_ORIGINS=https://queueme.net,https://shop.queueme.net,https://admin.queueme.net,https://api.queueme.net
  ```
- [ ] Configure rate limiting:
  ```
  RATE_LIMIT_DEFAULT_RATE=100
  RATE_LIMIT_DEFAULT_PERIOD=60
  RATE_LIMIT_API_RATE=60
  RATE_LIMIT_API_PERIOD=60
  RATE_LIMIT_OTP_RATE=5
  RATE_LIMIT_OTP_PERIOD=300
  ```

## Monitoring Setup

- [ ] Configure logging:
  ```bash
  mkdir -p /opt/queueme/logs
  chown -R queueme:queueme /opt/queueme/logs
  ```
- [ ] Set up log rotation:
  ```bash
  cp config/logrotate/queueme /etc/logrotate.d/
  ```
- [ ] Configure monitoring (optional):
  - Set up Prometheus and Grafana
  - Set up server monitoring (CPU, memory, disk usage)

## Cache and Redis Configuration

- [ ] Configure Redis:
  ```
  REDIS_HOST=localhost
  REDIS_PORT=6379
  REDIS_URL=redis://localhost:6379/1
  ```
- [ ] Configure cache settings:
  ```
  CACHE_TIMEOUT=300
  ```

## Final Verification

- [ ] Verify all services are running:
  ```bash
  systemctl status queueme queueme-daphne queueme-celery queueme-celery-beat nginx
  ```
- [ ] Check server logs for any errors:
  ```bash
  tail -f /opt/queueme/logs/*.log
  ```
- [ ] Verify the application is accessible at all configured domains:
  - https://queueme.net
  - https://shop.queueme.net
  - https://admin.queueme.net
  - https://api.queueme.net
- [ ] Test API endpoints and critical functionality
- [ ] Verify payment processing works correctly for all wallet types
- [ ] Check WebSocket connections are working

## Backup Configuration

- [ ] Set up regular database backups:
  ```bash
  cp scripts/backup_db.sh /etc/cron.daily/
  chmod +x /etc/cron.daily/backup_db.sh
  ```
- [ ] Configure media file backups:
  ```bash
  cp scripts/backup_media.sh /etc/cron.weekly/
  chmod +x /etc/cron.weekly/backup_media.sh
  ```

## Regular Maintenance Tasks

- [ ] Configure cron jobs for regular tasks:
  ```bash
  cp scripts/maintenance_tasks.sh /etc/cron.daily/
  chmod +x /etc/cron.daily/maintenance_tasks.sh
  ```
- [ ] Set up certificate renewal:
  ```bash
  certbot renew --dry-run  # Test renewal process
  ```
- [ ] Configure log rotation and cleanup:
  ```bash
  cp config/logrotate/queueme /etc/logrotate.d/
  ```

## Emergency Procedures

- [ ] Document rollback procedure
- [ ] Create disaster recovery plan
- [ ] Set up monitoring alerts
- [ ] Prepare incident response procedures

---

## Post-Deployment Checklist

- [ ] Verify SSL is properly configured and all pages load over HTTPS
- [ ] Test user registration and login process
- [ ] Test payment flow for all payment types
- [ ] Test WebSocket functionality
- [ ] Verify email sending works correctly
- [ ] Verify SMS sending works correctly
- [ ] Check performance under moderate load
- [ ] Run final security scan
- [ ] Verify all Moyasar webhook endpoints are receiving events
- [ ] Verify all Google Analytics/tracking is working (if applicable)

---

Remember to replace placeholder values with your actual production values. Keep this document confidential as it contains sensitive information.
