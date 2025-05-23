"""
Patch for schemathesis compatibility with Python 3.12

This script patches the schemathesis library to fix import errors
when running with Python 3.12.
"""

import sys
from pathlib import Path


def patch_schemathesis():
    """
    Patch the schemathesis library to fix compatibility issues with Python 3.12
    """
    # Find the schemathesis installation path
    try:
        import schemathesis

        schemathesis_path = Path(schemathesis.__file__).parent
        print(f"Found schemathesis at: {schemathesis_path}")

        # Path to the problematic file
        graphql_loaders_path = schemathesis_path / "specs" / "graphql" / "loaders.py"

        if not graphql_loaders_path.exists():
            print(f"Error: Could not find {graphql_loaders_path}")
            return False

        # Read the file content
        with open(graphql_loaders_path, "r") as f:
            content = f.read()

        # Fix the import statement
        if "DataGenerationMethodInput" in content:
            content = content.replace(
                "from ...generation import (\n    DEFAULT_DATA_GENERATION_METHODS,\n    DataGenerationMethod,\n    DataGenerationMethodInput,",
                "from ...generation import (\n    DEFAULT_DATA_GENERATION_METHODS,\n    DataGenerationMethod,",
            )

            # Create a backup
            backup_path = str(graphql_loaders_path) + ".bak"
            with open(backup_path, "w") as f:
                f.read(graphql_loaders_path)

            # Write the patched content
            with open(graphql_loaders_path, "w") as f:
                f.write(content)

            print(f"Successfully patched {graphql_loaders_path}")

            # Also create a mock class in generation/__init__.py
            generation_init_path = schemathesis_path / "generation" / "__init__.py"

            with open(generation_init_path, "r") as f:
                gen_content = f.read()

            if "class DataGenerationMethodInput" not in gen_content:
                # Add the missing class
                with open(generation_init_path, "a") as f:
                    f.write(
                        '\n\n# Added for Python 3.12 compatibility\nclass DataGenerationMethodInput:\n    """Mock class for backward compatibility"""\n    pass\n'
                    )

                print(f"Added compatibility class to {generation_init_path}")

            return True
        else:
            print("No need to patch, DataGenerationMethodInput not found in imports")
            return False

    except ImportError:
        print("Error: Could not import schemathesis")
        return False


if __name__ == "__main__":
    success = patch_schemathesis()
    sys.exit(0 if success else 1)
