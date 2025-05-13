"""
API Documentation Fix Utility for QueueMe

This module provides utilities to fix common issues in the auto-generated
API documentation, such as missing descriptions, incorrect data types, and
improving the overall documentation quality.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class APIDocsFixer:
    """Utility class to fix issues in API documentation."""

    def __init__(self, docs_dir: str = "static/api_docs"):
        """
        Initialize the APIDocsFixer.

        Args:
            docs_dir: Directory containing the API documentation files
        """
        self.docs_dir = Path(docs_dir)
        self.schema_file = self.docs_dir / "openapi-schema.json"
        self.fixed_issues = 0

    def fix_documentation(self) -> int:
        """
        Fix common issues in the API documentation.

        Returns:
            Number of issues fixed
        """
        logger.info(f"Fixing API documentation in {self.docs_dir}")

        # Reset counter
        self.fixed_issues = 0

        # Apply fixes in sequence
        self._fix_schema_if_exists()
        self._fix_html_files()

        logger.info(f"Fixed {self.fixed_issues} documentation issues")
        return self.fixed_issues

    def _fix_schema_if_exists(self) -> None:
        """Fix issues in the OpenAPI schema if it exists."""
        if not self.schema_file.exists():
            logger.warning(f"Schema file {self.schema_file} not found, skipping schema fixes")
            return

        try:
            with open(self.schema_file, "r") as f:
                schema = json.load(f)

            # Fix schema issues
            modified = False

            # Example: Fix missing operation IDs
            if "paths" in schema:
                for path, methods in schema["paths"].items():
                    for method, operation in methods.items():
                        if "operationId" not in operation:
                            # Generate an operationId based on path and method
                            path_name = path.replace("/", "_").strip("_")
                            operation["operationId"] = f"{method}_{path_name}"
                            modified = True
                            self.fixed_issues += 1

            # Example: Ensure all schemas have descriptions
            if "components" in schema and "schemas" in schema["components"]:
                for schema_name, schema_def in schema["components"]["schemas"].items():
                    if "description" not in schema_def:
                        schema_def["description"] = f"{schema_name} schema"
                        modified = True
                        self.fixed_issues += 1

            # Write fixed schema back if modified
            if modified:
                with open(self.schema_file, "w") as f:
                    json.dump(schema, f, indent=2)
                logger.info(f"Fixed OpenAPI schema at {self.schema_file}")

        except Exception as e:
            logger.error(f"Error fixing schema: {e}")

    def _fix_html_files(self) -> None:
        """Fix issues in HTML documentation files."""
        html_dir = self.docs_dir / "html"
        if not html_dir.exists():
            logger.warning(f"HTML directory {html_dir} not found, skipping HTML fixes")
            return

        try:
            # Process all HTML files
            for html_file in html_dir.glob("*.html"):
                logger.info(f"Checking {html_file}")
                # Read the file
                with open(html_file, "r") as f:
                    content = f.read()

                # Apply fixes to content
                fixed_content = self._apply_html_fixes(content)

                # Write back if modified
                if content != fixed_content:
                    with open(html_file, "w") as f:
                        f.write(fixed_content)
                    logger.info(f"Fixed HTML file {html_file}")

        except Exception as e:
            logger.error(f"Error fixing HTML files: {e}")

    def _apply_html_fixes(self, content: str) -> str:
        """
        Apply fixes to HTML content.

        Args:
            content: Original HTML content

        Returns:
            Fixed HTML content
        """
        # This is a placeholder for actual HTML fixes
        # In a real implementation, this would analyze and fix HTML content
        return content


def fix_api_docs(docs_dir: str = "static/api_docs") -> int:
    """
    Fix common issues in API documentation.

    Args:
        docs_dir: Directory containing the API documentation

    Returns:
        Number of issues fixed
    """
    fixer = APIDocsFixer(docs_dir)
    return fixer.fix_documentation()


def main():
    """Main entry point when script is run directly."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix issues in API documentation")
    parser.add_argument(
        "--dir",
        default="static/api_docs",
        help="Directory containing API documentation files",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Fix documentation issues
    num_fixes = fix_api_docs(args.dir)
    print(f"Fixed {num_fixes} documentation issues")


if __name__ == "__main__":
    main()
