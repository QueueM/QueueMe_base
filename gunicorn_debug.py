"""
Debug script to test Django startup without Gunicorn
"""

import os

import django

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")

# Initialize Django
django.setup()

# Import WSGI application

print("Django successfully initialized!")
print(f"Using settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")
