#!/usr/bin/env python3
"""
Script to extract all API endpoints from Django project
"""
import json
import os

from django.conf import settings
from django.urls import get_resolver

# Add project directory to path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.base")
import django

django.setup()


def extract_endpoints():
    """Extract all API endpoints from Django project"""
    resolver = get_resolver()
    endpoints = []

    def extract_patterns(resolver, prefix=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                # This is an include, recurse
                new_prefix = prefix + pattern.pattern.regex.pattern.lstrip("^").rstrip(
                    "$"
                )
                extract_patterns(pattern, new_prefix)
            else:
                # This is a URL pattern
                if hasattr(pattern, "callback") and pattern.callback:
                    callback_name = pattern.callback.__name__
                    module_name = pattern.callback.__module__

                    # Only include API endpoints
                    if "api" in module_name:
                        path = prefix + pattern.pattern.regex.pattern.lstrip(
                            "^"
                        ).rstrip("$")

                        # Extract HTTP methods
                        methods = []
                        if hasattr(pattern.callback, "cls") and hasattr(
                            pattern.callback.cls, "http_method_names"
                        ):
                            methods = [
                                m.upper()
                                for m in pattern.callback.cls.http_method_names
                                if m != "options"
                            ]
                        elif hasattr(pattern.callback, "actions"):
                            methods = [
                                m.upper() for m in pattern.callback.actions.keys()
                            ]
                        else:
                            # Default to GET if no methods specified
                            methods = ["GET"]

                        # Extract view class name if available
                        view_class = None
                        if hasattr(pattern.callback, "cls"):
                            view_class = pattern.callback.cls.__name__

                        endpoints.append(
                            {
                                "path": "/" + path,
                                "methods": methods,
                                "view": callback_name,
                                "view_class": view_class,
                                "module": module_name,
                            }
                        )

    extract_patterns(resolver)

    # Sort endpoints by path
    endpoints.sort(key=lambda x: x["path"])

    return endpoints


def check_swagger_docs():
    """Check if Swagger/OpenAPI documentation is available"""
    swagger_available = False
    swagger_url = None

    # Check if drf_yasg is in INSTALLED_APPS
    if hasattr(settings, "INSTALLED_APPS") and "drf_yasg" in settings.INSTALLED_APPS:
        swagger_available = True
        swagger_url = "/swagger/"

    return {"available": swagger_available, "url": swagger_url}


def main():
    """Main function"""
    endpoints = extract_endpoints()
    swagger_info = check_swagger_docs()

    result = {"endpoints": endpoints, "count": len(endpoints), "swagger": swagger_info}

    # Save to file
    with open("api_endpoints_extracted.json", "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"Extracted {len(endpoints)} API endpoints")
    print(
        f"Swagger documentation: {'Available' if swagger_info['available'] else 'Not available'}"
    )
    if swagger_info["available"] and swagger_info["url"]:
        print(f"Swagger URL: {swagger_info['url']}")

    # Print endpoints
    print("\nAPI Endpoints:")
    for endpoint in endpoints:
        methods = ", ".join(endpoint["methods"])
        print(
            f"{methods} {endpoint['path']} -> {endpoint['module']}.{endpoint['view']}"
        )

    return result


if __name__ == "__main__":
    main()
