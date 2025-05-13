# API Domain Setup Guide

This guide provides instructions for setting up the `api.queueme.net` domain with comprehensive API documentation.

## Overview

The API domain serves two primary purposes:
1. Providing API endpoints for the QueueMe platform
2. Hosting comprehensive API documentation for developers

## Prerequisites

- A server with Nginx installed
- SSL certificates for the domain
- Django application running with Gunicorn
- API documentation generated

## Step 1: Generate API Documentation

Run the API documentation generator script to create the documentation files:

```bash
# Make the script executable if it's not already
chmod +x generate_api_docs.sh

# Run the generator script
./generate_api_docs.sh
```

This will generate the documentation in the `static/swagger` and `static/api_docs` directories.

## Step 2: Configure Nginx

Create a dedicated Nginx configuration for the API domain:

1. Copy the provided configuration file:

```bash
sudo cp api-queueme-nginx.conf /etc/nginx/sites-available/api.queueme.net
```

2. Create a symbolic link to enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/api.queueme.net /etc/nginx/sites-enabled/
```

3. Test the Nginx configuration:

```bash
sudo nginx -t
```

4. Reload Nginx to apply the changes:

```bash
sudo systemctl reload nginx
```

## Step 3: Configure DNS

Configure DNS settings for the `api.queueme.net` domain to point to your server's IP address:

1. Add an A record for `api.queueme.net` pointing to your server's IP address.
2. If you're using a DNS provider like Cloudflare, ensure that SSL is properly configured.

## Step 4: Obtain SSL Certificate

If you don't already have an SSL certificate for the domain, you can obtain one using Let's Encrypt:

```bash
sudo certbot --nginx -d api.queueme.net
```

Follow the prompts to complete the certificate issuance process.

## Step 5: Verify Setup

Verify that the API domain is properly configured:

1. Open `https://api.queueme.net` in a web browser. You should see the API documentation landing page.
2. Navigate to `https://api.queueme.net/api/docs/swagger/` to verify that Swagger UI is working.
3. Test an API endpoint, for example: `https://api.queueme.net/api/health/`

## Documentation Structure

The API documentation is organized as follows:

- **Landing Page**: `https://api.queueme.net/` - Main API documentation landing page
- **Swagger UI**: `https://api.queueme.net/api/docs/swagger/` - Interactive API documentation
- **ReDoc**: `https://api.queueme.net/api/docs/redoc/` - Alternative API documentation view
- **OpenAPI Schema**: `https://api.queueme.net/api/schema.json` - Raw OpenAPI specification

## Maintenance

To update the API documentation:

1. Make changes to your API code or documentation
2. Run the API documentation generator script again:

```bash
./generate_api_docs.sh
```

3. Deploy the updated static files to the server

## Troubleshooting

### Documentation Not Updating

If the documentation isn't updating after generating new docs, try:

1. Clear the Nginx cache:

```bash
sudo rm -rf /var/cache/nginx/*
```

2. Reload Nginx:

```bash
sudo systemctl reload nginx
```

### API Endpoints Not Accessible

If API endpoints aren't accessible but documentation is:

1. Check that Gunicorn is running:

```bash
sudo systemctl status queueme
```

2. Check the Nginx error logs:

```bash
sudo tail -f /var/log/nginx/queueme-api.error.log
```

3. Check the application logs:

```bash
sudo tail -f /opt/queueme/logs/queueme.log
```

## Security Considerations

- Ensure that sensitive API endpoints are properly authenticated
- Consider rate limiting for public API endpoints
- Regularly update SSL certificates
- Monitor API usage for unusual patterns that might indicate abuse
