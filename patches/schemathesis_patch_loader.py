# Patch for schemathesis compatibility with Python 3.12
import sys
from types import ModuleType


# Create mock class for DataGenerationMethodInput
class MockDataGenerationMethodInput:
    """Mock class for backward compatibility"""



# Ensure the module exists
if "schemathesis" not in sys.modules:
    sys.modules["schemathesis"] = ModuleType("schemathesis")
if "schemathesis.generation" not in sys.modules:
    sys.modules["schemathesis.generation"] = ModuleType("schemathesis.generation")

# Add the mock class to the module
sys.modules["schemathesis.generation"].DataGenerationMethodInput = (
    MockDataGenerationMethodInput
)
