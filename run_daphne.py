import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")
django.setup()
application = get_asgi_application()

if __name__ == "__main__":
    import sys

    from daphne.cli import CommandLineInterface

    sys.argv = ["daphne", "-b", "0.0.0.0", "-p", "8000", "queueme.asgi:application"]
    CommandLineInterface.entrypoint()
