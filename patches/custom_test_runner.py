"""
Custom test runner for QueueMe that handles schemathesis compatibility issues
"""

import os
import sys
from pathlib import Path

# Apply schemathesis patch before importing pytest
patch_path = Path(__file__).parent / "schemathesis_patch_loader.py"
if patch_path.exists():
    print(f"Loading schemathesis compatibility patch from {patch_path}")
    exec(open(patch_path).read())

# Set environment variable to disable Swagger
os.environ["DISABLE_SWAGGER"] = "True"

# Mock drf_yasg to avoid circular imports
sys.modules["drf_yasg"] = type("MockDrfYasg", (), {})
sys.modules["drf_yasg.app_settings"] = type(
    "MockAppSettings", (), {"swagger_settings": {}}
)
sys.modules["drf_yasg.inspectors"] = type(
    "MockInspectors",
    (),
    {"base": type("MockBase", (), {"call_view_method": lambda x: None})},
)

# Now import pytest and run tests
import pytest

if __name__ == "__main__":
    # Use custom settings for testing
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.test")

    # Run pytest with specified arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/"]
    sys.exit(pytest.main(args))
