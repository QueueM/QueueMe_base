"""
Custom test runner that patches drf_yasg before Django loads
"""

import os
import sys

from django.test.runner import DiscoverRunner

# Patch drf_yasg before Django loads
sys.modules["drf_yasg"] = type("MockDrfYasg", (), {})
sys.modules["drf_yasg.app_settings"] = type(
    "MockAppSettings", (), {"swagger_settings": {}}
)
sys.modules["drf_yasg.inspectors"] = type(
    "MockInspectors",
    (),
    {"base": type("MockBase", (), {"call_view_method": lambda x: None})},
)

# Set environment variable to disable Swagger
os.environ["DISABLE_SWAGGER"] = "True"


class NoSwaggerTestRunner(DiscoverRunner):
    """Custom test runner that disables Swagger"""

    def __init__(self, *args, **kwargs):
        print("✅ Using custom test runner with Swagger disabled")
        super().__init__(*args, **kwargs)
