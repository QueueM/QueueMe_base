#!/bin/bash

# QueueMe Migration Script for Ubuntu 24.04 LTS
# =============================================
# This script prepares the QueueMe project to run on Ubuntu 24.04 LTS
# without using Docker.

set -e  # Exit immediately if a command exits with a non-zero status

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}      QueueMe Migration Script for Ubuntu 24.04      ${NC}"
echo -e "${GREEN}=====================================================${NC}"

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to log messages
log() {
    local message="$1"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "${GREEN}[${timestamp}]${NC} $message"
    echo "[${timestamp}] $message" >> logs/migration.log
}

# Function to check if a command is available
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to install packages if they're not already installed
install_package() {
    local package="$1"
    if dpkg -l | grep -q "^ii  $package "; then
        log "$package is already installed"
    else
        log "Installing $package..."
        sudo apt-get install -y "$package"
    fi
}

# Check for root privileges
if [ "$(id -u)" -eq 0 ]; then
    log "${RED}This script should not be run as root, but with a user that has sudo privileges${NC}"
    exit 1
fi

# 1. Update system packages
log "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Install required dependencies
log "Installing dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    postgresql \
    postgresql-contrib \
    postgresql-client \
    redis-server \
    nginx \
    libpq-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    supervisor \
    git \
    curl \
    wget \
    gdal-bin \
    libgdal-dev \
    binutils \
    libproj-dev

# Check PostgreSQL version
pg_version=$(psql --version | awk '{print $3}' | cut -d'.' -f1)
log "PostgreSQL version: $pg_version"

# 3. Setup PostgreSQL with PostGIS
log "Setting up PostgreSQL with PostGIS..."
sudo apt-get install -y postgis postgresql-${pg_version}-postgis-3

# 4. Configure PostgreSQL
log "Configuring PostgreSQL..."
# Create database user and database
sudo -u postgres psql -c "CREATE USER queueme WITH PASSWORD 'queueme' CREATEDB;" || log "User queueme may already exist"
sudo -u postgres psql -c "CREATE DATABASE queueme WITH OWNER queueme;" || log "Database queueme may already exist"
sudo -u postgres psql -d queueme -c "CREATE EXTENSION IF NOT EXISTS postgis;" || log "PostGIS extension may already exist"

# Enable PostgreSQL to start on boot
sudo systemctl enable postgresql
sudo systemctl restart postgresql

# 5. Configure Redis
log "Configuring Redis..."
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# 6. Setup Python virtual environment
log "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "Virtual environment created"
else
    log "Virtual environment already exists"
fi

# 7. Install Python dependencies
log "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install wheel setuptools
pip install -r requirements.txt

# 8. Setup environment variables
log "Setting up environment variables..."
if [ ! -f ".env" ]; then
    cp .env.example .env || echo "No .env.example file found"
    log "Please edit the .env file with your configuration settings"
else
    log ".env file already exists"
fi

# 9. Setup Nginx
log "Setting up Nginx..."
sudo tee /etc/nginx/sites-available/queueme <<EOF
server {
    listen 80;
    server_name _;  # Replace with your domain name if you have one

    client_max_body_size 100M;

    location /static/ {
        alias $(pwd)/staticfiles/;
    }

    location /media/ {
        alias $(pwd)/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/queueme /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Check Nginx config
sudo nginx -t && sudo systemctl restart nginx
sudo systemctl enable nginx

# 10. Setup Supervisord for Gunicorn and Daphne
log "Setting up Supervisord for Gunicorn and Daphne..."
sudo tee /etc/supervisor/conf.d/queueme.conf <<EOF
[program:queueme_gunicorn]
command=$(pwd)/venv/bin/gunicorn queueme.wsgi:application --workers 4 --bind 127.0.0.1:8000
directory=$(pwd)
user=$(whoami)
autostart=true
autorestart=true
stdout_logfile=$(pwd)/logs/gunicorn_out.log
stderr_logfile=$(pwd)/logs/gunicorn_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_daphne]
command=$(pwd)/venv/bin/daphne -b 127.0.0.1 -p 8001 queueme.asgi:application
directory=$(pwd)
user=$(whoami)
autostart=true
autorestart=true
stdout_logfile=$(pwd)/logs/daphne_out.log
stderr_logfile=$(pwd)/logs/daphne_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_celery]
command=$(pwd)/venv/bin/celery -A queueme worker --loglevel=info
directory=$(pwd)
user=$(whoami)
autostart=true
autorestart=true
stdout_logfile=$(pwd)/logs/celery_out.log
stderr_logfile=$(pwd)/logs/celery_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"

[program:queueme_celery_beat]
command=$(pwd)/venv/bin/celery -A queueme beat --loglevel=info
directory=$(pwd)
user=$(whoami)
autostart=true
autorestart=true
stdout_logfile=$(pwd)/logs/celery_beat_out.log
stderr_logfile=$(pwd)/logs/celery_beat_err.log
environment=DJANGO_SETTINGS_MODULE="queueme.settings.production"
EOF

sudo supervisorctl reread
sudo supervisorctl update

# 11. Setup firewall
log "Setting up firewall..."
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw allow 5432/tcp  # PostgreSQL
sudo ufw --force enable

# 12. Run Django migrations and collect static files
log "Running Django migrations and collecting static files..."
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=queueme.settings.production
python manage.py check
python manage.py collectstatic --noinput
python manage.py migrate

log "Migration script completed successfully!"
log "Please check the logs directory for any error messages."
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}       QueueMe Migration Complete! 🚀              ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Edit the ${YELLOW}.env${NC} file with your configuration"
echo -e "2. Set appropriate ${YELLOW}permissions${NC} for files and directories"
echo -e "3. Consider setting up ${YELLOW}SSL${NC} with Let's Encrypt"
echo -e "4. Review and modify the ${YELLOW}Nginx${NC} configuration as needed"
echo -e "5. Restart services: ${YELLOW}sudo supervisorctl restart all${NC}"
echo -e "${GREEN}=====================================================${NC}"
