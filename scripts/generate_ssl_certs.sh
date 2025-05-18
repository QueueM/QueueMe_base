#!/bin/bash
# =============================================================================
# QueueMe SSL Certificate Generation Script
# Generate Let's Encrypt SSL certificates for all QueueMe domains
# =============================================================================

set -e

# Configuration
EMAIL="admin@queueme.net"  # Change to your email
DOMAINS=(
    "queueme.net www.queueme.net"
    "shop.queueme.net"
    "admin.queueme.net"
    "api.queueme.net"
)
CERTBOT_PATH="/usr/bin/certbot"
WEBROOT="/var/www/certbot"
NGINX_RELOAD_CMD="systemctl reload nginx"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Create webroot if it doesn't exist
mkdir -p "$WEBROOT"

# Install certbot if not present
if [ ! -f "$CERTBOT_PATH" ]; then
    echo "Certbot not found. Installing..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
fi

# Generate certificates for each domain group
for domain_group in "${DOMAINS[@]}"; do
    primary_domain=$(echo "$domain_group" | cut -d' ' -f1)

    echo "Generating certificate for: $domain_group"

    # Check if certificate already exists and is not close to expiry
    if [ -d "/etc/letsencrypt/live/$primary_domain" ]; then
        expiry_date=$(openssl x509 -in "/etc/letsencrypt/live/$primary_domain/cert.pem" -enddate -noout | cut -d= -f2)
        expiry_epoch=$(date -d "$expiry_date" +%s)
        now_epoch=$(date +%s)
        days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

        if [ $days_left -gt 30 ]; then
            echo "Certificate for $primary_domain is still valid for $days_left days. Skipping renewal."
            continue
        fi
    fi

    # Build domain parameters
    domain_params=""
    for domain in $domain_group; do
        domain_params="$domain_params -d $domain"
    done

    # Generate or renew certificate
    $CERTBOT_PATH certonly --webroot -w "$WEBROOT" \
        --email "$EMAIL" --agree-tos --no-eff-email \
        $domain_params \
        --deploy-hook "$NGINX_RELOAD_CMD"

    echo "Certificate for $primary_domain has been generated/renewed."
done

# Create/update Diffie-Hellman parameters (if they don't exist or are old)
if [ ! -f /etc/letsencrypt/ssl-dhparams.pem ] || [ $(find /etc/letsencrypt/ssl-dhparams.pem -mtime +90 -print) ]; then
    echo "Generating Diffie-Hellman parameters (4096 bits, this will take some time)..."
    openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 4096
fi

# Create SSL recommended options
cat > /etc/letsencrypt/options-ssl-nginx.conf << 'EOF'
ssl_session_cache shared:le_nginx_SSL:10m;
ssl_session_timeout 1440m;
ssl_session_tickets off;

ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384";

ssl_stapling on;
ssl_stapling_verify on;
EOF

echo "All certificates have been processed successfully."
echo "Reloading Nginx..."
$NGINX_RELOAD_CMD

echo "Done!"
exit 0
