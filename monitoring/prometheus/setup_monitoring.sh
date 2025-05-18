#!/bin/bash
# QueueMe Monitoring Setup Script (Prometheus & Grafana)
# Run as root or with sudo

set -e

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root or with sudo" >&2
    exit 1
fi

MONITORING_DIR="/opt/queueme/monitoring"

echo "Setting up Prometheus and Grafana monitoring for QueueMe..."

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt update
    apt install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    apt update
    apt install -y docker-ce
fi

# Install Docker Compose if not already installed
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create directories
echo "Creating monitoring directories..."
mkdir -p $MONITORING_DIR
mkdir -p $MONITORING_DIR/prometheus/alerts
mkdir -p $MONITORING_DIR/grafana/provisioning/datasources
mkdir -p $MONITORING_DIR/grafana/provisioning/dashboards
mkdir -p $MONITORING_DIR/grafana/dashboards

# Copy configuration files
echo "Copying configuration files..."
cp -r $(dirname "$0")/* $MONITORING_DIR/

# Set proper permissions
chown -R root:root $MONITORING_DIR
chmod -R 755 $MONITORING_DIR

# Configure Nginx with Prometheus metrics endpoint
if [ -f /etc/nginx/nginx.conf ]; then
    echo "Configuring Nginx for Prometheus metrics..."
    # Check if the status module is already enabled
    if ! grep -q "stub_status" /etc/nginx/nginx.conf; then
        # Add status endpoint configuration
        cat >> /etc/nginx/conf.d/status.conf << 'EOF'
server {
    listen 127.0.0.1:80;
    server_name localhost;

    location /nginx_status {
        stub_status on;
        allow 127.0.0.1;
        deny all;
    }
}
EOF
        # Reload Nginx configuration
        systemctl reload nginx
    fi
fi

# Configure Django for Prometheus metrics
echo "Configuring Django for Prometheus metrics..."
pip install django-prometheus

# Start monitoring stack
echo "Starting monitoring stack..."
cd $MONITORING_DIR/prometheus
docker-compose up -d

echo "Monitoring setup completed!"
echo ""
echo "Prometheus is available at: http://your-server-ip:9090"
echo "Grafana is available at: http://your-server-ip:3000"
echo "Default Grafana login: admin/admin (please change the password after login)"
echo ""
echo "Remember to add django-prometheus to your Django settings and configure middleware!"
