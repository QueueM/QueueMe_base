#!/bin/bash
# QueueMe Production Server Setup Script
# For Ubuntu/Debian systems
# Run as root or with sudo

set -e

# Configuration variables
APP_NAME="queueme"
APP_USER="queueme"
APP_DIR="/opt/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/yourusername/QueueMe_base.git"  # Replace with your repo
GIT_BRANCH="main"
DOMAIN="example.com"  # Replace with your domain

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
    echo -e "${RED}[!] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[*] $1${NC}"
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    print_error "This script must be run as root or with sudo"
    exit 1
fi

# Update system packages
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install required system packages
print_status "Installing required system packages..."
apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib redis-server nginx supervisor \
    git curl wget ufw fail2ban \
    build-essential libpq-dev libssl-dev libffi-dev \
    certbot python3-certbot-nginx pgbouncer

# Create app user if it doesn't exist
if ! id -u "$APP_USER" &>/dev/null; then
    print_status "Creating application user: $APP_USER"
    useradd -m -s /bin/bash "$APP_USER"
else
    print_warning "User $APP_USER already exists, skipping creation"
fi

# Create app directory and set permissions
print_status "Creating application directory: $APP_DIR"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Setup PostgreSQL database
print_status "Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE USER $APP_USER WITH PASSWORD 'database_password';" || print_warning "User may already exist"
sudo -u postgres psql -c "CREATE DATABASE ${APP_NAME}_db OWNER $APP_USER;" || print_warning "Database may already exist"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${APP_NAME}_db TO $APP_USER;" || print_warning "Grant failed, may already have privileges"

# Setup PgBouncer
print_status "Configuring PgBouncer..."
cp "$APP_DIR/config/pgbouncer/pgbouncer.ini" /etc/pgbouncer/pgbouncer.ini
cp "$APP_DIR/config/pgbouncer/userlist.txt" /etc/pgbouncer/userlist.txt

# Restart PgBouncer service
print_status "Restarting PgBouncer service..."
systemctl restart pgbouncer
systemctl enable pgbouncer

# Clone the repository
print_status "Cloning the repository..."
sudo -u "$APP_USER" git clone "$REPO_URL" -b "$GIT_BRANCH" "$APP_DIR/repo"

# Setup virtual environment
print_status "Setting up Python virtual environment..."
sudo -u "$APP_USER" python3 -m venv "$VENV_DIR"
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip wheel

# Install dependencies
print_status "Installing Python dependencies..."
cd "$APP_DIR/repo"
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -r requirements.txt

# Setup environment variables
print_status "Setting up environment variables..."
cp "$APP_DIR/repo/.env.example" "$APP_DIR/repo/.env"
# You need to edit .env file with proper values after this script

# Setup Nginx
print_status "Configuring Nginx..."
cp "$APP_DIR/repo/queueme-nginx.conf" /etc/nginx/sites-available/$APP_NAME
sed -i "s/yourdomain.com/$DOMAIN/g" /etc/nginx/sites-available/$APP_NAME
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Remove default site

# Setup SSL with certbot
print_status "Setting up SSL with Let's Encrypt..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || print_warning "Certbot failed, check manually"

# Setup Supervisor
print_status "Configuring Supervisor..."
cp "$APP_DIR/repo/config/supervisor/queueme.conf" /etc/supervisor/conf.d/
sed -i "s|/path/to/queueme|$APP_DIR/repo|g" /etc/supervisor/conf.d/queueme.conf

# Setup Systemd services
print_status "Setting up Systemd services..."
cp "$APP_DIR/repo/queueme.service" "$APP_DIR/repo/queueme-celery.service" "$APP_DIR/repo/queueme-celery-beat.service" "$APP_DIR/repo/queueme-daphne.service" /etc/systemd/system/
systemctl daemon-reload

# Configure firewall
print_status "Configuring firewall..."
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp # HTTPS
ufw --force enable

# Configure fail2ban
print_status "Configuring fail2ban..."
cp "$APP_DIR/repo/config/fail2ban/jail.local" /etc/fail2ban/jail.local
systemctl restart fail2ban
systemctl enable fail2ban

# Run database migrations
print_status "Running database migrations..."
cd "$APP_DIR/repo"
sudo -u "$APP_USER" "$VENV_DIR/bin/python" manage.py migrate

# Collect static files
print_status "Collecting static files..."
sudo -u "$APP_USER" "$VENV_DIR/bin/python" manage.py collectstatic --no-input

# Start services
print_status "Starting application services..."
systemctl enable nginx
systemctl restart nginx
systemctl enable supervisor
systemctl restart supervisor
systemctl enable queueme queueme-celery queueme-celery-beat queueme-daphne
systemctl start queueme queueme-celery queueme-celery-beat queueme-daphne

# Setup monitoring cron job
print_status "Setting up monitoring..."
(crontab -l 2>/dev/null; echo "*/5 * * * * $VENV_DIR/bin/python $APP_DIR/repo/monitoring/alert_monitor.py") | crontab -

# Setup backup cron job
print_status "Setting up database backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * $VENV_DIR/bin/python $APP_DIR/repo/scripts/database_backup.py") | crontab -

print_status "Server setup complete!"
print_warning "IMPORTANT: You need to edit $APP_DIR/repo/.env with your actual credentials and settings"
print_warning "IMPORTANT: Review and update the PostgreSQL and PgBouncer passwords in /etc/pgbouncer/userlist.txt"
print_warning "IMPORTANT: Setup AWS S3 or Google Cloud Storage for media files in your .env file"

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}QueueMe has been installed successfully!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo ""
echo "You can access your site at: https://$DOMAIN"
echo ""
echo "To check status of services:"
echo "  systemctl status queueme"
echo "  systemctl status queueme-celery"
echo "  systemctl status queueme-daphne"
echo ""
echo "To check the logs:"
echo "  journalctl -u queueme"
echo "  tail -f $APP_DIR/repo/logs/queueme.log"
echo ""
