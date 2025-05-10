import os
import django
import sys

# Set up Django first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")
django.setup()

# Now import ASGI application after Django is ready
from queueme.asgi import application
from daphne.server import Server
from daphne.endpoints import build_endpoint_description_strings

# Run Daphne server
Server(
    application,
    endpoints=build_endpoint_description_strings(["tcp:port=8000:interface=0.0.0.0"]),
).run()
