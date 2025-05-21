"""
Debug script to test Django startup without Gunicorn
"""
import os
import sys
import django

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")

# Initialize Django
django.setup()

# Import WSGI application
from queueme.wsgi import application

print("Django successfully initialized!")
print(f"Using settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")
