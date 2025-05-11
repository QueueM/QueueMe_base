# File: /home/arise/queueme/generate_app_docs.py

#!/usr/bin/env python
"""
Script to automatically generate API documentation for all apps.
This will create api_docs.py files in each app directory.
"""

import os
import re
import importlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APPS_DIR = BASE_DIR / "apps"

APPS = [
    "authapp",
    "bookingapp",
    "categoriesapp",
    "chatapp",
    "companiesapp",
    "customersapp",
    "discountapp",
    "employeeapp",
    "followapp",
    "geoapp",
    "notificationsapp",
    "packageapp",
    "payment",
    "queueMeAdminApp",
    "queueapp",
    "reelsapp",
    "reportanalyticsapp",
    "reviewapp",
    "rolesapp",
    "serviceapp",
    "shopDashboardApp",
    "shopapp",
    "specialistsapp",
    "storiesapp",
    "subscriptionapp",
]

# Templates for api_docs.py files
def get_docs_template(app_name):
    """Generate documentation template for an app"""
    singular = app_name[:-3] if app_name.endswith('app') else app_name
    if singular.endswith('s'):
        singular = singular[:-1]
    
    class_name = singular.capitalize()
    
    return f'''"""
API Documentation helpers for {app_name}
"""
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers

# Example response serializers for documentation
class {class_name}Response(serializers.Serializer):
    id = serializers.IntegerField(help_text="{class_name} ID")
    name = serializers.CharField(help_text="{class_name} name", required=False)
    description = serializers.CharField(help_text="{class_name} description", required=False)
    # Add other fields based on your model

# Documentation decorators for viewsets
list_{app_name}_docs = swagger_auto_schema(
    operation_summary="List {app_name}",
    operation_description="Returns a paginated list of all {app_name}.",
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results per page", type=openapi.TYPE_INTEGER),
    ],
    responses={{
        200: "Success",
        401: "Unauthorized",
    }}
)

retrieve_{singular}_docs = swagger_auto_schema(
    operation_summary="Retrieve {singular}",
    operation_description="Returns a single {singular} by ID.",
    responses={{
        200: "Success",
        404: "Not found",
    }}
)

create_{singular}_docs = swagger_auto_schema(
    operation_summary="Create {singular}",
    operation_description="Creates a new {singular}.",
    responses={{
        201: "Created successfully",
        400: "Bad request",
    }}
)

update_{singular}_docs = swagger_auto_schema(
    operation_summary="Update {singular}",
    operation_description="Updates an existing {singular}.",
    responses={{
        200: "Updated successfully",
        404: "Not found",
    }}
)

delete_{singular}_docs = swagger_auto_schema(
    operation_summary="Delete {singular}",
    operation_description="Deletes an existing {singular}.",
    responses={{
        204: "Deleted successfully",
        404: "Not found",
    }}
)

# Add more custom endpoint documentation decorators as needed
'''

def create_docs_file(app_name):
    """Create api_docs.py file for an app"""
    app_dir = APPS_DIR / app_name
    docs_file = app_dir / "api_docs.py"
    
    if not docs_file.exists():
        with open(docs_file, 'w') as f:
            f.write(get_docs_template(app_name))
        print(f"Created {docs_file}")
    else:
        print(f"File {docs_file} already exists, skipping")

def apply_docs_to_views(app_name):
    """Apply documentation decorators to views in the app"""
    app_dir = APPS_DIR / app_name
    views_file = app_dir / "views.py"
    
    if not views_file.exists():
        print(f"No views.py found for {app_name}, skipping")
        return
    
    # Read views file
    with open(views_file, 'r') as f:
        content = f.read()
    
    # Check if we need to add import
    if "from .api_docs import" not in content:
        # Determine what to import
        import_line = f"from .api_docs import list_{app_name}_docs, retrieve_{app_name[:-3] if app_name.endswith('app') else app_name}_docs"
        
        # Add import after other imports
        import_section_end = max(content.rfind("import "), content.rfind("from "))
        if import_section_end > 0:
            # Find the line after the last import
            line_end = content.find("\n", import_section_end)
            if line_end > 0:
                new_content = content[:line_end+1] + "\n" + import_line + "\n" + content[line_end+1:]
                
                # Write back to file
                with open(views_file, 'w') as f:
                    f.write(new_content)
                
                print(f"Added documentation imports to {views_file}")
            else:
                print(f"Could not find a good place to add imports in {views_file}")
        else:
            print(f"No imports found in {views_file}")
    else:
        print(f"Documentation imports already exist in {views_file}")

def generate_docs_for_all_apps():
    """Generate documentation for all apps"""
    for app_name in APPS:
        try:
            create_docs_file(app_name)
            apply_docs_to_views(app_name)
        except Exception as e:
            print(f"Error processing {app_name}: {e}")

if __name__ == "__main__":
    # Set up Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.production')
    import django
    django.setup()
    
    print("Generating documentation for all apps...")
    generate_docs_for_all_apps()
    print("Documentation generation complete!")
