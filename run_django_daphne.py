import os
import sys

import django
from daphne.endpoints import build_endpoint_description_strings
from daphne.server import Server

from queueme.asgi import application

# Set up Django first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")
django.setup()


# Now import ASGI application after Django is ready

# Run Daphne server
Server(
    application,
    endpoints=build_endpoint_description_strings(["tcp:port=8000:interface=0.0.0.0"]),
).run()
