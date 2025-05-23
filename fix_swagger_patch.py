"""
Patch to fix drf-yasg circular import issues
"""

import os
import sys

# Add this to prevent drf_yasg from being imported during test setup
os.environ["DISABLE_SWAGGER"] = "True"

# Monkey patch drf_yasg to prevent circular imports
sys.modules["drf_yasg"] = type("MockDrfYasg", (), {})
sys.modules["drf_yasg.app_settings"] = type(
    "MockAppSettings", (), {"swagger_settings": {}}
)
sys.modules["drf_yasg.inspectors"] = type(
    "MockInspectors",
    (),
    {"base": type("MockBase", (), {"call_view_method": lambda x: None})},
)

print("✅ Swagger patched to prevent circular imports")
