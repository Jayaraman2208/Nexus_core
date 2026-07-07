from django.urls import re_path

from .consumers import NetworkMetricsConsumer

websocket_urlpatterns = [
    re_path(r"ws/network-metrics/$", NetworkMetricsConsumer.as_asgi()),
]
