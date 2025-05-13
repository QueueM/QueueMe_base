#!/bin/bash
# UFW Setup Script for QueueMe Production Server
# Run as root

set -e

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

echo "Setting up UFW firewall for QueueMe production server..."

# Reset UFW to default settings
ufw --force reset

# Default deny incoming traffic, allow outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow SSH
echo "Allowing SSH connections..."
ufw allow ssh
# Alternative: ufw allow 22/tcp

# Allow HTTP/HTTPS
echo "Allowing HTTP and HTTPS connections..."
ufw allow 80/tcp
ufw allow 443/tcp

# Rate limit SSH connections
echo "Setting up rate limiting for SSH connections..."
ufw limit ssh

# Optional: Allow other services if needed
# For example, if you need to access PostgreSQL directly (not recommended):
# ufw allow from trusted-ip-address to any port 5432 proto tcp

# Enable UFW
echo "Enabling UFW..."
ufw --force enable

# Show status
ufw status verbose

echo "UFW setup complete!"
echo "The server now only allows connections on ports 22 (SSH), 80 (HTTP), and 443 (HTTPS)."
