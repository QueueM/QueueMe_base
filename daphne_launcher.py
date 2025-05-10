#!/usr/bin/env python3
"""
Custom launcher for Daphne that ensures Django is properly initialized.
This avoids the "Apps aren't loaded yet" error when importing models.
"""

import os
import sys
import django
from django.core.wsgi import get_wsgi_application

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.production')
django.setup()

# Now it's safe to import and run Daphne
from daphne.cli import CommandLineInterface

# Run Daphne with the same arguments passed to this script
sys.argv[0] = 'daphne'
CommandLineInterface.entrypoint() 