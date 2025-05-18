from django.urls import re_path

from apps.specialistsapp.consumers import SpecialistStatusConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/specialists/(?P<specialist_id>[0-9a-f-]+)/status/$",
        SpecialistStatusConsumer.as_asgi(),
    ),
]
