#!/bin/bash

# API Documentation Generator Script for QueueMe
# Generates comprehensive API documentation for api.queueme.net

set -e  # Exit on error

echo "🚀 QueueMe API Documentation Generator"
echo "======================================="

# Create output directories
mkdir -p static/swagger
mkdir -p static/api_docs

# Generate API documentation
echo "📝 Generating API documentation..."
python api_docs_generator.py --output-dir static/swagger --verbose

# Copy the landing page to api_docs directory
echo "🌐 Setting up landing page..."
cp static/api_docs/index.html static/swagger/

# Apply documentation fixes
echo "🔧 Applying documentation fixes..."
python api_docs_fix.py --dir static/swagger

# Set proper permissions
echo "🔒 Setting proper permissions..."
find static/swagger -type f -exec chmod 644 {} \;
find static/api_docs -type f -exec chmod 644 {} \;

echo "✅ API documentation generated successfully!"
echo "📊 Documentation is available at:"
echo "  - Landing page: /static/api_docs/index.html"
echo "  - Swagger UI: /static/swagger/swagger-ui.html"
echo "  - ReDoc: /static/swagger/redoc.html"
echo "  - OpenAPI Schema: /static/swagger/swagger.json"

echo ""
echo "📌 Next steps:"
echo "1. Deploy the static files to the web server"
echo "2. Configure Nginx using api-queueme-nginx.conf"
echo "3. Restart Nginx to apply changes"
echo ""
