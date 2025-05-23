#!/usr/bin/env python
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Now set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.production')

import django
django.setup()

# Run the command
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
