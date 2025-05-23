"""
Minimal test runner for QueueMe backend

This module provides a minimal test runner that completely excludes problematic
dependencies to enable stable test execution.
"""

import os
import sys

from django.test.runner import DiscoverRunner


class MinimalTestRunner(DiscoverRunner):
    """
    Minimal test runner that excludes problematic dependencies and uses
    simplified test settings.
    """

    def __init__(self, *args, **kwargs):
        # Set environment variables to disable problematic components
        os.environ["DISABLE_SWAGGER"] = "True"
        os.environ["DISABLE_SCHEMATHESIS"] = "True"

        # Mock problematic modules before they're imported
        # Create minimal mocks with all required attributes to prevent attribute errors
        mock_attributes = {
            "__file__": "",
            "__loader__": type("MockLoader", (), {"exec_module": lambda x, y: None}),
            "__path__": [],
            "__package__": "",
            "__spec__": None,
        }

        # Mock drf_yasg
        sys.modules["drf_yasg"] = type("MockDrfYasg", (), mock_attributes)
        sys.modules["drf_yasg.app_settings"] = type(
            "MockAppSettings", (), {**mock_attributes, "swagger_settings": {}}
        )
        sys.modules["drf_yasg.inspectors"] = type(
            "MockInspectors",
            (),
            {
                **mock_attributes,
                "base": type("MockBase", (), {"call_view_method": lambda x: None}),
            },
        )

        # Mock schemathesis
        sys.modules["schemathesis"] = type("MockSchemathesis", (), mock_attributes)

        # Mock django_compressor
        sys.modules["compressor"] = type("MockCompressor", (), mock_attributes)
        sys.modules["django_compressor"] = type(
            "MockDjangoCompressor", (), mock_attributes
        )

        print("✅ Using minimal test runner with mocked dependencies")
        super().__init__(*args, **kwargs)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """
        Run tests with minimal settings and mocked dependencies.
        """
        if not test_labels:
            # Default to running core unit tests if no specific tests are specified
            test_labels = ["tests.unit.core"]

        print(f"Running tests with labels: {test_labels}")
        return super().run_tests(test_labels, extra_tests, **kwargs)


def main():
    """
    Main function to run tests using the minimal test runner.
    """
    from django.core.management import execute_from_command_line

    # Set Django settings module to our minimal test settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "minimal_test_settings")

    # Prepare test command
    test_command = [
        "manage.py",
        "test",
        "--testrunner=minimal_test_runner.MinimalTestRunner",
    ]

    # Add any additional arguments
    if len(sys.argv) > 1:
        test_command.extend(sys.argv[1:])

    # Run tests
    execute_from_command_line(test_command)


if __name__ == "__main__":
    main()
