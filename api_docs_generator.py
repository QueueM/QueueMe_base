#!/usr/bin/env python

"""
API Documentation Generator for QueueMe

This script generates comprehensive API documentation for the QueueMe platform
by analyzing and documenting all API endpoints, models, and serializers.

Features:
- Auto-generates documentation for all API endpoints
- Creates interactive Swagger documentation
- Generates static HTML documentation with beautiful styling
- Optimizes documentation for developer usability
- Supports multiple output formats (JSON, YAML, HTML)

Usage:
    python api_docs_generator.py [options]

Options:
    --output-dir DIR    Output directory [default: static/swagger]
    --format FORMAT     Output format (json, yaml, html, all) [default: all]
    --theme THEME       Documentation theme (default, dark, material) [default: material]
    --title TITLE       API title [default: QueueMe API]
    --version VERSION   API version [default: v1]
    --verbose           Verbose output
"""

import argparse
import importlib
import inspect
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_docs_generator")


class APIDocumentationGenerator:
    """
    Generates comprehensive API documentation for the QueueMe platform.

    This class analyzes the Django project structure, extracts API endpoints,
    models, and serializers, and generates interactive and static documentation.
    """

    def __init__(
        self,
        output_dir: str = "static/swagger",
        format: str = "all",
        theme: str = "material",
        title: str = "QueueMe API",
        version: str = "v1",
        verbose: bool = False,
    ):
        """
        Initialize the API documentation generator.

        Args:
            output_dir: Output directory for documentation
            format: Output format (json, yaml, html, all)
            theme: Documentation theme
            title: API title
            version: API version
            verbose: Enable verbose output
        """
        self.output_dir = Path(output_dir)
        self.format = format
        self.theme = theme
        self.title = title
        self.version = version
        self.verbose = verbose

        # Configure logging
        self._setup_logging()

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize empty collections
        self.tags = set()
        self.models = {}
        self.serializers = {}
        self.viewsets = []
        self.endpoints = []

        # Set up Django environment
        self.setup_django()

        # Discover viewsets
        self.viewsets = self.discover_viewsets()

    def _setup_logging(self):
        """Configure logging based on verbose flag."""
        if self.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def setup_django(self):
        """Set up Django environment for API documentation generation."""
        logger.info("Setting up Django environment...")

        try:
            # Initialize Django
            import django

            django.setup()

            # Check if Django is properly set up
            from django.apps import apps

            apps.check_apps_ready()

            # Import Django REST Framework
            import rest_framework

            logger.info("Django environment set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up Django environment: {str(e)}")
            raise

    def discover_apps(self) -> List[str]:
        """
        Discover all app names in the Django project.

        Returns:
            List of app names
        """
        self.setup_django()

        from django.apps import apps

        app_configs = apps.get_app_configs()

        # Filter to include only our apps
        our_apps = [
            app.name
            for app in app_configs
            if app.name.startswith("apps.") or app.name.startswith("api")
        ]

        logger.info(f"Discovered {len(our_apps)} apps")
        return our_apps

    def discover_viewsets(self) -> List[Any]:
        """Discover API viewsets in the project."""
        viewsets = []
        for app_name in self.discover_apps():
            try:
                views_module = importlib.import_module(f"{app_name}.views")
                for name, obj in inspect.getmembers(views_module):
                    if (
                        inspect.isclass(obj)
                        and name.endswith("ViewSet")
                        and not name.startswith("_")
                    ):
                        viewsets.append(obj)
                        logger.debug(f"Found viewset: {obj.__module__}.{obj.__name__}")
            except (ImportError, ModuleNotFoundError):
                # Not all apps have a views module
                continue

        logger.info(f"Discovered {len(viewsets)} viewset classes")
        self.viewsets = viewsets  # Store for later use
        return viewsets

    def discover_models(self) -> Dict[str, Any]:
        """
        Discover all models in the Django project.

        Returns:
            Dictionary mapping model names to model classes
        """
        self.setup_django()

        from django.db import models

        model_dict = {}
        apps = self.discover_apps()

        for app_name in apps:
            # Try to import app's models module
            try:
                models_module = importlib.import_module(f"{app_name}.models")

                # Inspect module members
                for name, obj in inspect.getmembers(models_module):
                    # Check if this is a model class
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, models.Model)
                        and obj != models.Model
                    ):
                        model_dict[f"{obj.__module__}.{obj.__name__}"] = obj
                        logger.debug(f"Found model: {obj.__module__}.{obj.__name__}")
            except (ImportError, ModuleNotFoundError):
                pass

        logger.info(f"Discovered {len(model_dict)} model classes")
        return model_dict

    def discover_serializers(self) -> Dict[str, Any]:
        """
        Discover all serializers in the Django project.

        Returns:
            Dictionary mapping serializer names to serializer classes
        """
        self.setup_django()

        from rest_framework import serializers

        serializer_dict = {}
        apps = self.discover_apps()

        for app_name in apps:
            # Try to import app's serializers module
            try:
                serializers_module = importlib.import_module(f"{app_name}.serializers")

                # Inspect module members
                for name, obj in inspect.getmembers(serializers_module):
                    # Check if this is a serializer class
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, serializers.Serializer)
                        and obj != serializers.Serializer
                        and obj != serializers.ModelSerializer
                    ):
                        serializer_dict[f"{obj.__module__}.{obj.__name__}"] = obj
                        logger.debug(f"Found serializer: {obj.__module__}.{obj.__name__}")
            except (ImportError, ModuleNotFoundError):
                pass

        logger.info(f"Discovered {len(serializer_dict)} serializer classes")
        return serializer_dict

    def extract_endpoints(self) -> List[Dict[str, Any]]:
        """Extract API endpoints from registered viewsets."""
        from rest_framework import routers

        # Create a router to extract URL patterns
        router = routers.SimpleRouter()
        endpoints = []

        # Register all viewsets with the router
        for viewset in self.viewsets:
            name = self._get_viewset_name(viewset)
            router.register(f"temp/{name}", viewset, basename=name)

        # Create a fresh router for each viewset to avoid URL conflicts
        for viewset in self.viewsets:
            temp_router = routers.SimpleRouter()
            name = self._get_viewset_name(viewset)
            temp_router.register(f"temp/{name}", viewset, basename=name)

            # Process URLs from this router
            for url_pattern in temp_router.urls:
                # Extract endpoint information
                path = self._format_path(url_pattern.pattern)
                name = url_pattern.name
                method = self._get_method_from_action(
                    url_pattern.callback.actions if hasattr(url_pattern.callback, "actions") else {}
                )

                # Extract docstring from view method
                docstring = self._get_method_docstring(url_pattern.callback)

                # Get serializer class for this endpoint
                serializer_class = self._get_serializer_class(url_pattern.callback)

                # Extract tags from viewset module name
                module_parts = viewset.__module__.split(".")
                app_name = module_parts[1] if len(module_parts) > 1 else "api"
                tags = [app_name]

                endpoints.append(
                    {
                        "path": path,
                        "name": name,
                        "method": method,
                        "description": docstring,
                        "serializer": (serializer_class.__name__ if serializer_class else None),
                        "tags": tags,
                        "viewset": viewset.__name__,
                    }
                )

        logger.info(f"Extracted {len(endpoints)} endpoints from {len(self.viewsets)} viewsets")
        return endpoints

    def generate_openapi_schema(self) -> Dict[str, Any]:
        """
        Generate OpenAPI schema from endpoints, models, and serializers.

        Returns:
            OpenAPI schema as dictionary
        """
        # Initialize schema
        schema = {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": (
                    "QueueMe platform API provides endpoints for managing bookings, services, "
                    "queues, specialists, and customer interactions efficiently. "
                    "The API supports features such as real-time notifications, "
                    "payment processing, and scheduling."
                ),
                "contact": {
                    "name": "QueueMe Support",
                    "url": "https://queueme.net/support",
                    "email": "support@queueme.net",
                },
                "termsOfService": "https://queueme.net/terms",
            },
            "servers": [
                {
                    "url": "https://api.queueme.net",
                    "description": "Production API server",
                },
                {
                    "url": "https://staging-api.queueme.net",
                    "description": "Staging API server",
                },
                {
                    "url": "http://localhost:8000",
                    "description": "Local development server",
                },
            ],
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    }
                },
            },
            "tags": [{"name": tag} for tag in sorted(self.tags)],
            "security": [{"bearerAuth": []}],
        }

        # Discover data
        self.models = self.discover_models()
        self.serializers = self.discover_serializers()
        self.endpoints = self.extract_endpoints()

        # Generate paths
        for endpoint in self.endpoints:
            path = endpoint["path"]
            method = endpoint["method"].lower()

            # Initialize path if not exists
            if path not in schema["paths"]:
                schema["paths"][path] = {}

            # Add method to path
            schema["paths"][path][method] = {
                "tags": endpoint["tags"],
                "summary": (
                    endpoint["description"].split("\n")[0] if endpoint["description"] else ""
                ),
                "description": endpoint["description"],
                "responses": {
                    "200": {"description": "Successful operation"},
                    "400": {"description": "Bad request"},
                    "401": {"description": "Unauthorized"},
                    "403": {"description": "Forbidden"},
                    "404": {"description": "Not found"},
                    "500": {"description": "Server error"},
                },
            }

        logger.info("Generated OpenAPI schema")
        return schema

    def generate_documentation(self):
        """Generate API documentation in the specified format."""
        # Generate OpenAPI schema
        schema = self.generate_openapi_schema()

        # Determine formats to generate
        formats = []
        if self.format == "all":
            formats = ["json", "yaml", "html"]
        else:
            formats = [self.format]

        # Generate documentation in each format
        for fmt in formats:
            if fmt == "json":
                self._generate_json_schema(schema)
            elif fmt == "yaml":
                self._generate_yaml_schema(schema)
            elif fmt == "html":
                self._generate_html_documentation(schema)

        # Generate index.html
        self._generate_index_html()

        logger.info(f"Documentation generated in {self.output_dir}")

    def _generate_json_schema(self, schema: Dict[str, Any]):
        """
        Generate JSON schema file.

        Args:
            schema: OpenAPI schema dictionary
        """
        output_file = self.output_dir / "openapi.json"

        with open(output_file, "w") as f:
            json.dump(schema, f, indent=2)

        logger.info(f"Generated JSON schema: {output_file}")

    def _generate_yaml_schema(self, schema: Dict[str, Any]):
        """
        Generate YAML schema file.

        Args:
            schema: OpenAPI schema dictionary
        """
        try:
            import yaml

            output_file = self.output_dir / "openapi.yaml"

            with open(output_file, "w") as f:
                yaml.dump(schema, f, default_flow_style=False)

            logger.info(f"Generated YAML schema: {output_file}")
        except ImportError:
            logger.warning("PyYAML not installed. Skipping YAML schema generation.")

    def _generate_html_documentation(self, schema: Dict[str, Any]):
        """
        Generate HTML documentation.

        Args:
            schema: OpenAPI schema dictionary
        """
        # Save schema for Swagger UI
        swagger_file = self.output_dir / "swagger.json"
        with open(swagger_file, "w") as f:
            json.dump(schema, f, indent=2)

        # Create Swagger UI HTML
        self._generate_swagger_html()

        # Create ReDoc HTML
        self._generate_redoc_html()

        logger.info(f"Generated HTML documentation in {self.output_dir}")

    def _generate_swagger_html(self):
        """Generate Swagger UI HTML."""
        output_file = self.output_dir / "swagger-ui.html"

        # Swagger UI template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title} Documentation - Swagger UI</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.5.0/swagger-ui.css" />
    <link rel="icon" type="image/png" href="https://queueme.net/favicon.ico" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}

        *,
        *:before,
        *:after {{
            box-sizing: inherit;
        }}

        body {{
            margin: 0;
            background: #fafafa;
        }}

        .swagger-ui .topbar {{
            background-color: #1a365d;
        }}

        .swagger-ui .info .title {{
            color: #2563eb;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>

    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.5.0/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.5.0/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                url: "./swagger.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "BaseLayout",
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
                defaultModelRendering: 'model',
                docExpansion: 'list',
                filter: true,
                operationsSorter: 'alpha',
                showCommonExtensions: true,
                tagsSorter: 'alpha',
                validatorUrl: null,
                supportedSubmitMethods: ['get', 'post', 'put', 'delete', 'patch'],
            }});

            window.ui = ui;
        }};
    </script>
</body>
</html>
"""

        with open(output_file, "w") as f:
            f.write(html)

        logger.info(f"Generated Swagger UI HTML: {output_file}")

    def _generate_redoc_html(self):
        """Generate ReDoc HTML."""
        output_file = self.output_dir / "redoc.html"

        # ReDoc template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title} Documentation - ReDoc</title>
    <link rel="icon" type="image/png" href="https://queueme.net/favicon.ico" />
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url="./swagger.json"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
</body>
</html>
"""

        with open(output_file, "w") as f:
            f.write(html)

        logger.info(f"Generated ReDoc HTML: {output_file}")

    def _generate_index_html(self):
        """Generate index.html with links to documentation variants."""
        output_file = self.output_dir / "index.html"

        # Calculate current year at the beginning, before using it in template
        import datetime

        current_year = datetime.datetime.now().year

        # Index template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title} Documentation</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
    <link rel="icon" type="image/png" href="https://queueme.net/favicon.ico" />
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1a365d;
            --secondary: #10b981;
            --dark: #1f2937;
            --gray: #6b7280;
            --light-gray: #f3f4f6;
            --border: #e5e7eb;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.6;
            color: var(--dark);
            background-color: #f9fafb;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: linear-gradient(to right, var(--primary-dark), var(--primary));
            color: white;
            padding: 4rem 0;
            text-align: center;
        }}

        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
        }}

        h1 {{
            margin-bottom: 1rem;
            font-weight: 700;
            font-size: 2.5rem;
        }}

        p {{
            margin-bottom: 1.5rem;
            font-size: 1.25rem;
            opacity: 0.9;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
            flex: 1;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }}

        .card {{
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
        }}

        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        }}

        .card-header {{
            background-color: var(--primary);
            color: white;
            padding: 1.5rem;
        }}

        .card-header h2 {{
            margin: 0;
            font-size: 1.5rem;
        }}

        .card-content {{
            padding: 1.5rem;
            flex: 1;
        }}

        .card-footer {{
            padding: 1.5rem;
            border-top: 1px solid var(--border);
            text-align: center;
        }}

        .btn {{
            display: inline-block;
            background-color: var(--primary);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 0.25rem;
            text-decoration: none;
            font-weight: 500;
            transition: background-color 0.2s;
        }}

        .btn:hover {{
            background-color: var(--primary-dark);
        }}

        .btn-secondary {{
            background-color: white;
            color: var(--primary);
            border: 1px solid var(--primary);
        }}

        .btn-secondary:hover {{
            background-color: var(--light-gray);
        }}

        footer {{
            background-color: white;
            border-top: 1px solid var(--border);
            padding: 2rem 0;
            text-align: center;
            color: var(--gray);
        }}

        @media (max-width: 768px) {{
            .cards {{
                grid-template-columns: 1fr;
            }}

            header {{
                padding: 3rem 0;
            }}

            h1 {{
                font-size: 2rem;
            }}

            p {{
                font-size: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <h1>{self.title} Documentation</h1>
            <p>Complete reference for the QueueMe platform API</p>
        </div>
    </header>

    <div class="container">
        <p>
            Welcome to the QueueMe API documentation. The QueueMe platform provides a RESTful API for
            building applications that integrate with the QueueMe ecosystem. Use the documentation
            options below to explore the available endpoints and learn how to use them.
        </p>

        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <h2>Swagger UI</h2>
                </div>
                <div class="card-content">
                    <p>Interactive documentation with Swagger UI. Try out API calls directly in your browser.</p>
                </div>
                <div class="card-footer">
                    <a href="./swagger-ui.html" class="btn">View Swagger UI</a>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>ReDoc</h2>
                </div>
                <div class="card-content">
                    <p>Clean and responsive API documentation with a three-panel, easy-to-read layout.</p>
                </div>
                <div class="card-footer">
                    <a href="./redoc.html" class="btn">View ReDoc</a>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>OpenAPI Schema</h2>
                </div>
                <div class="card-content">
                    <p>Raw OpenAPI schema in JSON format for integrating with tools and code generators.</p>
                </div>
                <div class="card-footer">
                    <a href="./swagger.json" class="btn">JSON Schema</a>
                    <a href="./openapi.yaml" class="btn btn-secondary">YAML Schema</a>
                </div>
            </div>
        </div>
    </div>

    <footer>
        <div>© {current_year} QueueMe. All rights reserved.</div>
    </footer>
</body>
</html>
"""

        with open(output_file, "w") as f:
            f.write(html)

        logger.info(f"Generated index HTML: {output_file}")

    def _get_viewset_name(self, viewset):
        """Extract a name for the viewset to be used as basename."""
        name = viewset.__name__
        if name.endswith("ViewSet"):
            name = name[:-7].lower()
        return name

    def _format_path(self, pattern):
        """Format the URL pattern into a clean path."""
        if hasattr(pattern, "regex"):
            # Django <2.0 style
            path = pattern.regex.pattern
        elif hasattr(pattern, "_route"):
            # Django 2.0+ style
            path = pattern._route
        else:
            # Fallback for other pattern types
            path = str(pattern)

        # Clean up the path
        path = path.replace("^", "")
        path = path.replace("\\Z", "")
        path = path.replace("$", "")
        path = f"/api/{path}" if not path.startswith("/api") else path
        return path

    def _get_method_from_action(self, actions):
        """Get the HTTP method from action mapping."""
        # Default to GET if no action mapping is found
        if not actions:
            return "GET"

        # Find the first non-options method
        for method, action in actions.items():
            if method != "options":
                return method.upper()

        return "GET"

    def _get_method_docstring(self, callback):
        """Extract the docstring from the callback method."""
        docstring = ""

        if hasattr(callback, "__doc__") and callback.__doc__:
            docstring = callback.__doc__

        # Try to get a more specific docstring from the handler method
        if hasattr(callback, "actions"):
            method_name = next(iter(callback.actions.values()), None)
            if method_name and hasattr(callback.cls, method_name):
                method = getattr(callback.cls, method_name)
                if method.__doc__:
                    docstring = method.__doc__

        return docstring.strip() if docstring else ""

    def _get_serializer_class(self, callback):
        """Get the serializer class associated with the callback."""
        serializer_class = None

        if hasattr(callback, "cls") and hasattr(callback.cls, "get_serializer_class"):
            try:
                view_instance = callback.cls()
                serializer_class = view_instance.get_serializer_class()
            except Exception:
                # Fallback to serializer_class attribute if get_serializer_class fails
                if hasattr(callback.cls, "serializer_class"):
                    serializer_class = callback.cls.serializer_class

        return serializer_class


def main():
    """Main function for the API documentation generator."""
    parser = argparse.ArgumentParser(description="Generate API documentation for QueueMe")
    parser.add_argument("--output-dir", default="static/swagger", help="Output directory")
    parser.add_argument(
        "--format",
        choices=["json", "yaml", "html", "all"],
        default="all",
        help="Output format",
    )
    parser.add_argument(
        "--theme",
        choices=["default", "dark", "material"],
        default="material",
        help="Documentation theme",
    )
    parser.add_argument("--title", default="QueueMe API", help="API title")
    parser.add_argument("--version", default="v1", help="API version")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Generate API documentation
    generator = APIDocumentationGenerator(
        output_dir=args.output_dir,
        format=args.format,
        theme=args.theme,
        title=args.title,
        version=args.version,
        verbose=args.verbose,
    )

    generator.generate_documentation()


if __name__ == "__main__":
    main()
