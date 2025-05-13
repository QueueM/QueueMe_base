import logging
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy as _


class Command(BaseCommand):
    help = "Generate API documentation for api.queueme.net"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="static/swagger",
            help="Output directory for Swagger documentation",
        )
        parser.add_argument(
            "--landing-dir",
            default="static/api_docs",
            help="Output directory for API landing page",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing documentation",
        )
        parser.add_argument(
            "--format",
            choices=["json", "yaml", "html", "all"],
            default="all",
            help="Output format for documentation",
        )

    def handle(self, *args, **options):
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger = logging.getLogger("api_docs")

        # Get parameters
        output_dir = options["output_dir"]
        landing_dir = options["landing_dir"]
        force = options["force"]
        doc_format = options["format"]

        # Create output directories
        output_path = Path(output_dir)
        landing_path = Path(landing_dir)

        output_path.mkdir(parents=True, exist_ok=True)
        landing_path.mkdir(parents=True, exist_ok=True)

        # Check if documentation already exists and if we should overwrite
        if not force and (output_path / "swagger.json").exists():
            self.stdout.write(
                self.style.WARNING("API documentation already exists. Use --force to overwrite.")
            )
            return

        # Generate API documentation
        self.stdout.write(self.style.HTTP_INFO("Generating API documentation..."))

        try:
            # Run the API documentation generator
            from api_docs_generator import APIDocumentationGenerator

            # Initialize the generator
            generator = APIDocumentationGenerator(
                output_dir=str(output_path),
                format=doc_format,
                title="QueueMe API",
                version="v1",
                verbose=True,
            )

            # Generate documentation
            generator.generate_documentation()

            # Copy landing page index.html to output directory
            if (landing_path / "index.html").exists():
                if not (output_path / "index.html").exists() or force:
                    # Copy the file
                    from shutil import copy

                    copy(landing_path / "index.html", output_path / "index.html")
                    self.stdout.write(self.style.SUCCESS("Copied landing page to output directory"))

            # Apply fixes if api_docs_fix.py exists
            api_docs_fix_path = Path("api_docs_fix.py")
            if api_docs_fix_path.exists():
                self.stdout.write(self.style.HTTP_INFO("Applying documentation fixes..."))

                try:
                    from api_docs_fix import fix_api_docs

                    num_fixes = fix_api_docs(str(output_path))
                    self.stdout.write(
                        self.style.SUCCESS(f"Applied {num_fixes} documentation fixes")
                    )
                except ImportError:
                    self.stdout.write(
                        self.style.WARNING("Could not import api_docs_fix. Skipping fixes.")
                    )

            # Set proper permissions
            for file_path in output_path.glob("**/*"):
                if file_path.is_file():
                    os.chmod(file_path, 0o644)

            for file_path in landing_path.glob("**/*"):
                if file_path.is_file():
                    os.chmod(file_path, 0o644)

            # Success message
            self.stdout.write(self.style.SUCCESS("API documentation generated successfully!"))
            self.stdout.write(self.style.HTTP_INFO("Documentation is available at:"))
            self.stdout.write(f"  - Swagger UI: /{output_dir}/swagger-ui.html")
            self.stdout.write(f"  - ReDoc: /{output_dir}/redoc.html")
            self.stdout.write(f"  - OpenAPI Schema: /{output_dir}/swagger.json")

        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    "Could not import api_docs_generator. Make sure it's in your Python path."
                )
            )
            raise CommandError("API documentation generation failed")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating API documentation: {e}"))
            raise CommandError(f"API documentation generation failed: {e}")
