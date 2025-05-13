# QueueMe API Documentation System

This document provides an overview of the API documentation system implemented for the QueueMe platform.

## Components

The API documentation system consists of the following components:

1. **API Documentation Generator** (`api_docs_generator.py`): A Python script that analyzes the Django project structure to automatically generate API documentation.

2. **API Documentation Fixer** (`api_docs_fix.py`): A utility to fix common issues in the generated documentation.

3. **Landing Page** (`static/api_docs/index.html`): A beautiful, responsive landing page for the API documentation.

4. **Swagger UI**: Interactive API documentation allowing developers to test API endpoints directly in the browser.

5. **ReDoc**: An alternative, responsive API documentation view with a three-panel layout.

6. **OpenAPI Schema**: Raw JSON and YAML specifications for integration with other tools.

7. **Nginx Configuration** (`api-queueme-nginx.conf`): Server configuration for hosting the API documentation.

8. **Generator Script** (`generate_api_docs.sh`): A shell script to automate the documentation generation process.

## Features

### API Documentation Generator

The generator automatically:

- Discovers all API endpoints in the QueueMe platform
- Extracts documentation from docstrings and annotations
- Organizes endpoints by tags based on app name and viewset name
- Generates comprehensive OpenAPI 3.0 schema
- Creates multiple documentation formats (JSON, YAML, HTML)

### Landing Page

The landing page provides:

- Modern, responsive design with clean typography
- Sections for features, getting started, and examples
- Code snippets for common API operations
- Frequently asked questions section
- Call-to-action for developers

### Interactive Documentation

Swagger UI offers:

- Interactive testing of API endpoints
- Authentication support
- Request and response examples
- Schema definitions
- Filtering and search capabilities

### API Domain

The dedicated `api.queueme.net` domain:

- Serves API endpoints
- Hosts comprehensive documentation
- Provides OpenAPI schema for integration
- Includes proper security headers and CORS configuration
- Optimized for developer experience

## Directory Structure

```
QueueMe_base/
├── api_docs_generator.py        # Documentation generator
├── api_docs_fix.py              # Documentation fixer
├── generate_api_docs.sh         # Generator script
├── api-queueme-nginx.conf       # Nginx configuration
├── API_DOMAIN_SETUP.md          # Setup guide
├── API_DOCUMENTATION_SUMMARY.md # This summary
├── static/
│   ├── api_docs/                # Landing page
│   │   └── index.html           # Main landing page
│   └── swagger/                 # Generated documentation
│       ├── index.html           # Documentation index
│       ├── swagger-ui.html      # Swagger UI
│       ├── redoc.html           # ReDoc
│       ├── swagger.json         # OpenAPI schema (JSON)
│       └── openapi.yaml         # OpenAPI schema (YAML)
```

## Workflow

1. **Development**: Developers document API endpoints using docstrings and annotations.

2. **Generation**: Run `./generate_api_docs.sh` to generate documentation.

3. **Deployment**: Deploy the static files to the server and configure Nginx.

4. **Usage**: Developers access the documentation at `https://api.queueme.net`.

## Future Improvements

- **Authentication Documentation**: Expand documentation on authentication methods.
- **Versioning**: Add support for API versioning in the documentation.
- **Code Samples**: Generate code samples for multiple programming languages.
- **Rate Limiting**: Document rate limits for each endpoint.
- **Search**: Add full-text search capability to the documentation.
- **Interactive Tutorials**: Add guided tutorials for common API operations.

## Conclusion

The QueueMe API documentation system provides a comprehensive, developer-friendly interface for exploring and using the QueueMe API. It combines automatic documentation generation with beautiful presentation to create a seamless developer experience.
