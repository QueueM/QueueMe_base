"""
Django management command to generate API documentation.

This command uses our custom API documentation generator to create
comprehensive documentation for all endpoints in the QueueMe platform.
"""

import logging
import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate comprehensive API documentation for QueueMe"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="static/api_docs",
            help="Output directory for documentation files",
        )
        parser.add_argument(
            "--format",
            choices=["html", "json", "all"],
            default="all",
            help="Output format for documentation",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regeneration of documentation",
        )

    def handle(self, *args, **options):
        output_dir = options["output"]
        output_format = options["format"]
        # Commented out since not used currently - fix for F841
        # force = options['force']

        # Ensure the project root is in sys.path
        from django.conf import settings

        sys.path.insert(0, str(settings.BASE_DIR))

        # Import the API documentation generator
        try:
            from api_docs_generator import APIDocumentationGenerator

            # Create output directory if it doesn't exist
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            self.stdout.write(f"Generating API documentation in {output_dir}...")

            # Initialize the documentation generator
            generator = APIDocumentationGenerator()

            # Generate documentation based on the specified format
            if output_format == "all" or output_format == "html":
                generator.generate_documentation()
                self.stdout.write(self.style.SUCCESS("HTML documentation generated successfully"))

            if output_format == "all" or output_format == "json":
                # If we haven't already generated everything
                if output_format == "json":
                    # First discover endpoints and models
                    generator.discover_api_endpoints()
                    generator.discover_models_and_serializers()
                    # Then just write the JSON file
                    generator._write_json_data()
                    self.stdout.write(self.style.SUCCESS("JSON data generated successfully"))

                # Also generate OpenAPI schema as a separate file
                generator._generate_openapi_schema()
                self.stdout.write(self.style.SUCCESS("OpenAPI schema generated successfully"))

            self.stdout.write(
                self.style.SUCCESS(f"API documentation successfully generated in {output_dir}")
            )

        except ImportError as e:
            self.stderr.write(self.style.ERROR(f"Failed to import documentation generator: {e}"))
            self.stderr.write(
                self.style.WARNING("Make sure api_docs_generator.py is in your project root")
            )
            return

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error generating API documentation: {e}"))
            import traceback

            self.stderr.write(traceback.format_exc())
            return
