#!/usr/bin/env python
import os
import sys

# Set the settings module explicitly
os.environ['DJANGO_SETTINGS_MODULE'] = 'queueme.settings.production'

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Django and set it up
import django
django.setup()

# Now run the deployment check
from django.core.management import call_command
call_command('check', '--deploy')
