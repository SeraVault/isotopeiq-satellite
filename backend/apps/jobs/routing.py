from django.urls import re_path
from . import consumers
from apps.drift import consumers as drift_consumers

websocket_urlpatterns = [
    re_path(r'ws/jobs/$', consumers.JobStatusConsumer.as_asgi()),
    re_path(r'ws/drift/$', drift_consumers.DriftConsumer.as_asgi()),
]
