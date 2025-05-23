"""
Custom compatibility module for schemathesis with Python 3.12

This module provides compatibility fixes for running schemathesis with Python 3.12,
specifically addressing the missing DataGenerationMethodInput class issue.
"""

import os
from pathlib import Path


def create_mock_class():
    """
    Create a mock DataGenerationMethodInput class in the schemathesis.generation module
    """
    mock_code = """
# Added for Python 3.12 compatibility
class DataGenerationMethodInput:
    \"\"\"Mock class for backward compatibility\"\"\"
    pass
"""
    return mock_code


def patch_module():
    """
    Patch the schemathesis module to fix compatibility issues with Python 3.12
    """
    # Create a patch that can be applied before importing schemathesis
    patch_code = """
# Patch for schemathesis compatibility with Python 3.12
import sys
from types import ModuleType

# Create mock class for DataGenerationMethodInput
class MockDataGenerationMethodInput:
    \"\"\"Mock class for backward compatibility\"\"\"
    pass

# Ensure the module exists
if 'schemathesis' not in sys.modules:
    sys.modules['schemathesis'] = ModuleType('schemathesis')
if 'schemathesis.generation' not in sys.modules:
    sys.modules['schemathesis.generation'] = ModuleType('schemathesis.generation')
    
# Add the mock class to the module
sys.modules['schemathesis.generation'].DataGenerationMethodInput = MockDataGenerationMethodInput
"""
    return patch_code


def create_test_runner():
    """
    Create a custom test runner that applies the schemathesis patch
    """
    test_runner_code = """
"""
    return test_runner_code


def main():
    """
    Main function to create and apply the compatibility fixes
    """
    # Create the patch file
    patch_file = Path("/home/arise/QueueMe_base/patches/schemathesis_patch_loader.py")
    with open(patch_file, "w") as f:
        f.write(patch_module())
    print(f"Created patch file: {patch_file}")

    # Create a custom test runner that uses the patch
    custom_runner_file = Path("/home/arise/QueueMe_base/patches/custom_test_runner.py")
    with open(custom_runner_file, "w") as f:
        f.write(
            """
\"\"\"
Custom test runner for QueueMe that handles schemathesis compatibility issues
\"\"\"
import os
import sys
from pathlib import Path

# Apply schemathesis patch before importing pytest
patch_path = Path(__file__).parent / 'schemathesis_patch_loader.py'
if patch_path.exists():
    print(f"Loading schemathesis compatibility patch from {patch_path}")
    exec(open(patch_path).read())

# Set environment variable to disable Swagger
os.environ['DISABLE_SWAGGER'] = 'True'

# Mock drf_yasg to avoid circular imports
sys.modules['drf_yasg'] = type('MockDrfYasg', (), {})
sys.modules['drf_yasg.app_settings'] = type('MockAppSettings', (), {'swagger_settings': {}})
sys.modules['drf_yasg.inspectors'] = type('MockInspectors', (), {'base': type('MockBase', (), {'call_view_method': lambda x: None})})

# Now import pytest and run tests
import pytest

if __name__ == '__main__':
    # Use custom settings for testing
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.test')
    
    # Run pytest with specified arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ['tests/']
    sys.exit(pytest.main(args))
"""
        )
    print(f"Created custom test runner: {custom_runner_file}")

    # Create a shell script to run tests with the custom runner
    run_tests_script = Path("/home/arise/QueueMe_base/run_tests.sh")
    with open(run_tests_script, "w") as f:
        f.write(
            """#!/bin/bash
# Run tests with custom test runner that handles schemathesis compatibility

# Activate virtual environment
source venv/bin/activate

# Run the custom test runner
python patches/custom_test_runner.py "$@"
"""
        )
    os.chmod(run_tests_script, 0o755)  # Make executable
    print(f"Created test runner script: {run_tests_script}")

    print("\nCompatibility fixes created successfully!")
    print("To run tests, use: ./run_tests.sh [test_path]")


if __name__ == "__main__":
    main()
