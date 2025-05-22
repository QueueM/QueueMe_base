#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


# --------------------------------------------------------------------------
# SWAGGER DEBUG PATCH: Print all OpenAPI parameters per endpoint
# --------------------------------------------------------------------------
def swagger_debug_patch():
    try:
        from drf_yasg.inspectors import SwaggerAutoSchema

        real_get_operation = SwaggerAutoSchema.get_operation

        def debug_get_operation(self, operation_keys=None):
            op = real_get_operation(self, operation_keys)
            try:
                print(
                    "\n==== YASG DEBUG: Endpoint:",
                    getattr(self.view, "__class__", type(self.view)).__name__,
                )
                if hasattr(op, "parameters"):
                    names = [
                        (getattr(p, "name", None), getattr(p, "in_", None))
                        for p in op.parameters
                    ]
                    print(
                        "OpenAPI params for",
                        getattr(self.view, "__class__", type(self.view)).__name__,
                        ":",
                        names,
                    )
                else:
                    print(
                        "No op.parameters for",
                        getattr(self.view, "__class__", type(self.view)).__name__,
                    )
            except Exception as e:
                print("DEBUG ERROR", e)
            return op

        SwaggerAutoSchema.get_operation = debug_get_operation
        print("Swagger debug patch applied.")
    except Exception as e:
        print("Failed to patch Swagger:", e)


swagger_debug_patch()


# --------------------------------------------------------------------------
def main():
    """Run administrative tasks."""
    # Check if DJANGO_SETTINGS_MODULE is already set in the environment
    # Only default to development if not already set
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        print("No settings module specified, defaulting to development settings")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.development")
    else:
        print(f"Using settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
