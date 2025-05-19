# websockets/apps.py
from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "websockets"              # dotted path to the package
    label = "queueme_websockets"     # unique label → avoids clashing with PyPI “websockets”
