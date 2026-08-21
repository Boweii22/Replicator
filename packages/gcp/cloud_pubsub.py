from __future__ import annotations

import os

from packages.schemas.models import WorkMessage


class CloudEventBus:
    def __init__(self, project: str | None = None) -> None:
        from google.cloud import pubsub_v1

        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.publisher = pubsub_v1.PublisherClient()

    async def publish(self, topic: str, message: WorkMessage) -> None:
        path = self.publisher.topic_path(self.project, topic)
        future = self.publisher.publish(path, message.model_dump_json().encode(),
            event_type=message.event_type)
        future.result(timeout=30)
