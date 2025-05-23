#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    # Load environment variables FIRST
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(BASE_DIR / '.env')
    
    # Now set up Django
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
