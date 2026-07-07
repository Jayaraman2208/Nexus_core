import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NetworkMetricsConsumer(AsyncWebsocketConsumer):
    """
    Streams live network metrics to authenticated dashboard clients.
    Backed by the 'network_metrics' channel layer group, which the
    `broadcast_live_metrics` Celery task publishes to periodically.
    """

    GROUP_NAME = "network_metrics"

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def metrics_update(self, event):
        """Handler name maps to the 'type': 'metrics.update' message sent via group_send."""
        await self.send(text_data=json.dumps(event["data"]))
