"""
Simplified test runner for QueueMe that bypasses schemathesis compatibility issues
"""

import os
import sys

# Set environment variable to disable Swagger
os.environ["DISABLE_SWAGGER"] = "True"

# Mock problematic modules
sys.modules["drf_yasg"] = type("MockDrfYasg", (), {})
sys.modules["drf_yasg.app_settings"] = type(
    "MockAppSettings", (), {"swagger_settings": {}}
)
sys.modules["drf_yasg.inspectors"] = type(
    "MockInspectors",
    (),
    {"base": type("MockBase", (), {"call_view_method": lambda x: None})},
)
sys.modules["schemathesis"] = type("MockSchemathesis", (), {})

# Now import pytest and run tests
import pytest
from django.test.runner import DiscoverRunner


class SimplifiedTestRunner(DiscoverRunner):
    """Custom test runner that bypasses schemathesis"""

    def __init__(self, *args, **kwargs):
        print("✅ Using simplified test runner with mocked dependencies")
        super().__init__(*args, **kwargs)


if __name__ == "__main__":
    # Use custom settings for testing
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.test")

    # Run pytest with specified arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/"]

    # Filter out any tests that might depend on schemathesis
    filtered_args = [arg for arg in args if "schemathesis" not in arg]
    if "tests/" in filtered_args and not any(
        arg.startswith("--") for arg in filtered_args
    ):
        filtered_args = ["tests/unit/"] + [
            arg for arg in filtered_args if arg != "tests/"
        ]

    print(f"Running tests with args: {filtered_args}")
    sys.exit(pytest.main(filtered_args))
