from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

from packages.schemas.models import WorkMessage

Handler = Callable[[WorkMessage], Awaitable[None]]


class LocalEventBus:
    def __init__(self) -> None:
        self.handlers: dict[str, list[Handler]] = defaultdict(list)
        self.tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self.handlers[topic].append(handler)

    async def publish(self, topic: str, message: WorkMessage) -> None:
        for handler in self.handlers[topic]:
            task = asyncio.create_task(handler(message))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def drain(self) -> None:
        while self.tasks:
            await asyncio.gather(*tuple(self.tasks))


bus = LocalEventBus()
