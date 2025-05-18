# QueueMe API Documentation System

This document provides comprehensive instructions for deploying and using the QueueMe API documentation system available at `https://api.queueme.net`.

## Overview

The QueueMe API documentation system provides a rich, interactive documentation experience for all APIs in the QueueMe platform. The documentation is designed to be developer-friendly, with multiple presentation formats, code examples, and interactive features.

## Components

The API documentation system consists of the following components:

1. **Modern Landing Page** (`static/api_docs/index.html`): A beautiful, responsive landing page with dark mode support that provides an overview of the API documentation and links to various documentation formats. Features include:
   - Interactive UI with animations and transitions
   - Light/dark mode toggle
   - Code examples in multiple programming languages
   - Quick access to popular endpoints
   - Mobile-responsive design

2. **Swagger UI** (`static/swagger/swagger-ui.html`): An enhanced interactive documentation interface that allows developers to explore and test API endpoints directly in the browser. Our customized version includes:
   - Custom branded header and styling
   - Quick start guide for new developers
   - Interactive authentication assistant
   - Endpoint examples and usage patterns
   - Improved visual hierarchy and readability

3. **ReDoc** (`static/swagger/redoc.html`): A clean, responsive documentation view with a three-panel layout optimized for readability. The customized version includes:
   - Branded header with navigation
   - Customized theme matching QueueMe branding
   - Optimized typography and spacing
   - Enhanced request/response examples

4. **API Guide** (`static/api_docs/api_guide.html`): A comprehensive guide with detailed examples and best practices for using the API, featuring:
   - Step-by-step instructions for common workflows
   - Interactive code samples in multiple languages
   - Authentication guides
   - Error handling documentation
   - Best practices and security recommendations

5. **OpenAPI Schemas**: Machine-readable API specifications in JSON and YAML formats for integration with development tools and code generators.

## Documentation Generation

The API documentation is generated using the following tools:

1. **API Documentation Generator** (`api_docs_generator.py`): Analyzes the Django project structure to automatically generate comprehensive API documentation.

2. **Django Management Command** (`apps/payment/management/commands/generate_api_docs.py`): A Django command to generate and update API documentation.

3. **Shell Script** (`generate_api_docs.sh`): A convenient shell script that runs the documentation generator and applies fixes.

## Deployment

### Prerequisites

- Nginx web server
- Django application with drf-yasg installed
- SSL certificates for the domain

### Step 1: Generate API Documentation

Run the API documentation generator to create the documentation files:

```bash
# Make the script executable
chmod +x generate_api_docs.sh

# Run the generator script
./generate_api_docs.sh
```

Alternatively, you can use the Django management command:

```bash
python manage.py generate_api_docs --force
```

This will generate the documentation in the `static/swagger` and `static/api_docs` directories.

### Step 2: Configure Nginx

Deploy the `api-queueme-nginx.conf` configuration file to your Nginx sites directory:

```bash
sudo cp api-queueme-nginx.conf /etc/nginx/sites-available/api-queueme.conf
sudo ln -s /etc/nginx/sites-available/api-queueme.conf /etc/nginx/sites-enabled/
```

The Nginx configuration handles:
- Proper routing for the `api.queueme.net` domain
- Serving static documentation files
- Proxying API requests to the Django application
- SSL configuration
- Security headers
- Caching for static assets

### Step 3: Test and Reload Nginx

Test the Nginx configuration and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 4: Verify Installation

Visit the following URLs to verify the documentation is properly deployed:

- Landing page: `https://api.queueme.net/`
- Swagger UI: `https://api.queueme.net/docs/swagger/`
- ReDoc: `https://api.queueme.net/docs/redoc/`
- API Guide: `https://api.queueme.net/docs/guide/`

## Maintenance and Updates

### Updating Documentation

When API endpoints or models change, regenerate the documentation:

```bash
python manage.py generate_api_docs --force
```

### Customizing the Documentation

The documentation styling can be customized by editing the HTML files:

- Landing page: `static/api_docs/index.html`
- Swagger UI: `static/swagger/swagger-ui.html`
- ReDoc: `static/swagger/redoc.html`
- API Guide: `static/api_docs/api_guide.html`

### Adding New Examples

To add new code examples or use cases:

1. Edit the appropriate HTML file
2. Add the example code with proper syntax highlighting
3. Update the navigation links if necessary

## Troubleshooting

### Common Issues

1. **Documentation not updating**: Make sure you're using the `--force` flag when regenerating documentation.

2. **Swagger UI not loading**: Check your browser console for JavaScript errors, and ensure that the `swagger.json` file is accessible.

3. **CSS/styling issues**: Check for missing static files or incorrect paths in the HTML files.

4. **Permission errors**: Ensure that Nginx has proper permissions to read the documentation files.

## Advanced Configuration

### Authentication for Documentation

To require authentication for accessing the documentation:

1. Edit the `api-queueme-nginx.conf` file
2. Add basic authentication directives
3. Generate a password file using `htpasswd`

### Custom Domain for Documentation Only

To serve documentation on a separate domain (e.g., `docs.queueme.net`):

1. Create a new Nginx configuration file for the documentation domain
2. Configure DNS records for the new domain
3. Obtain SSL certificates for the new domain
