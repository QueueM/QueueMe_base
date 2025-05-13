#!/bin/bash
# ModSecurity installation and configuration script for QueueMe
# Run with sudo on Ubuntu/Debian systems

set -e

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root or with sudo"
    exit 1
fi

echo "Installing ModSecurity and dependencies..."

# Install required packages
apt update
apt install -y nginx libnginx-mod-http-headers-more-filter \
    apt-utils autoconf automake build-essential git libcurl4-openssl-dev \
    libgeoip-dev liblmdb-dev libpcre++-dev libtool libxml2-dev libyajl-dev \
    pkgconf wget zlib1g-dev

# Clone and build ModSecurity
cd /usr/local/src/
git clone --depth 1 -b v3/master --single-branch https://github.com/SpiderLabs/ModSecurity
cd ModSecurity
git submodule init
git submodule update
./build.sh
./configure
make
make install

# Clone and build the Nginx connector for ModSecurity
cd /usr/local/src/
git clone --depth 1 https://github.com/SpiderLabs/ModSecurity-nginx.git
wget -O - http://nginx.org/download/nginx-$(nginx -v 2>&1 | sed 's/^.*nginx\///;s/ .*$//').tar.gz | tar zxf -
cd nginx-$(nginx -v 2>&1 | sed 's/^.*nginx\///;s/ .*$//')
./configure --with-compat --add-dynamic-module=/usr/local/src/ModSecurity-nginx
make modules
mkdir -p /etc/nginx/modules
cp objs/ngx_http_modsecurity_module.so /etc/nginx/modules/

# Configure Nginx to load the ModSecurity module
echo 'load_module modules/ngx_http_modsecurity_module.so;' > /etc/nginx/modules-enabled/50-mod-http-modsecurity.conf

# Clone OWASP Core Rule Set
cd /etc/nginx/
git clone -b v3.3/master --depth 1 https://github.com/coreruleset/coreruleset modsecurity-crs
cd modsecurity-crs
cp crs-setup.conf.example crs-setup.conf

# Set up basic ModSecurity configuration
cp /usr/local/src/ModSecurity/modsecurity.conf-recommended /etc/nginx/modsecurity.conf

# Copy QueueMe's custom configuration
cp /opt/queueme/repo/config/nginx/modsecurity.conf /etc/nginx/modsecurity_custom.conf

# Create unicode mapping file
wget -O /etc/nginx/unicode.mapping https://raw.githubusercontent.com/SpiderLabs/ModSecurity/v3/master/unicode.mapping

# Update Nginx server configuration to include ModSecurity
for CONF in /etc/nginx/sites-enabled/*; do
    # Skip if already configured
    if grep -q "modsecurity on" "$CONF"; then
        continue
    fi

    # Add ModSecurity configuration block inside server block
    sed -i '/server {/a \    # ModSecurity configuration\n    modsecurity on;\n    modsecurity_rules_file /etc/nginx/modsecurity.conf;\n    modsecurity_rules_file /etc/nginx/modsecurity_custom.conf;\n' "$CONF"
done

# Test Nginx configuration
nginx -t

# Restart Nginx to apply changes
systemctl restart nginx

echo "ModSecurity has been installed and configured successfully!"
echo "OWASP Core Rule Set is installed in /etc/nginx/modsecurity-crs/"
echo "Custom rules are in /etc/nginx/modsecurity_custom.conf"
