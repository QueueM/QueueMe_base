"""
Custom Django test runner for QueueMe backend

This module provides a custom test runner that bypasses problematic dependencies
like schemathesis and drf_yasg, allowing for stable test execution.
"""

import os
import sys

from django.test.runner import DiscoverRunner


class CustomTestRunner(DiscoverRunner):
    """
    Custom test runner that bypasses problematic dependencies and uses
    simplified test settings.
    """

    def __init__(self, *args, **kwargs):
        # Set Django settings module to our custom test settings
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.test")

        # Mock problematic modules before they're imported
        sys.modules["drf_yasg"] = type(
            "MockDrfYasg",
            (),
            {
                "__file__": "",
                "__loader__": type("MockLoader", (), {}),
                "__path__": [],
                "__package__": "",
                "__spec__": None,
            },
        )
        sys.modules["drf_yasg.app_settings"] = type(
            "MockAppSettings",
            (),
            {
                "swagger_settings": {},
                "__file__": "",
                "__loader__": type("MockLoader", (), {}),
                "__path__": [],
                "__package__": "",
                "__spec__": None,
            },
        )
        sys.modules["drf_yasg.inspectors"] = type(
            "MockInspectors",
            (),
            {
                "base": type("MockBase", (), {"call_view_method": lambda x: None}),
                "__file__": "",
                "__loader__": type("MockLoader", (), {}),
                "__path__": [],
                "__package__": "",
                "__spec__": None,
            },
        )

        # Create a more complete mock for schemathesis
        mock_schemathesis = type(
            "MockSchemathesis",
            (),
            {
                "__file__": "",
                "__loader__": type("MockLoader", (), {}),
                "__path__": [],
                "__package__": "",
                "__spec__": None,
            },
        )
        sys.modules["schemathesis"] = mock_schemathesis

        # Set environment variable to disable Swagger
        os.environ["DISABLE_SWAGGER"] = "True"

        print("✅ Using custom test runner with mocked dependencies")
        super().__init__(*args, **kwargs)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """
        Run tests with custom settings and mocked dependencies.
        """
        if not test_labels:
            # Default to running unit tests if no specific tests are specified
            test_labels = ["tests.unit"]

        print(f"Running tests with labels: {test_labels}")
        return super().run_tests(test_labels, extra_tests, **kwargs)


def main():
    """
    Main function to run tests using the custom test runner.
    """
    from django.core.management import execute_from_command_line

    # Set Django settings module to our custom test settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "custom_test_settings")

    # Prepare test command
    test_command = [
        "manage.py",
        "test",
        "--testrunner=custom_test_runner.CustomTestRunner",
    ]

    # Add any additional arguments
    if len(sys.argv) > 1:
        test_command.extend(sys.argv[1:])

    # Run tests
    execute_from_command_line(test_command)


if __name__ == "__main__":
    main()
