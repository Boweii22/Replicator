from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator

from packages.schemas.models import Claim, Event, Replication, ReplicationStatus, utcnow


class ConflictError(RuntimeError):
    pass


class InMemoryState:
    """Local Firestore substitute. Locks model transaction boundaries used in cloud mode."""

    def __init__(self) -> None:
        self.replications: dict[str, Replication] = {}
        self.processed_events: set[str] = set()
        self.events: dict[str, list[Event]] = defaultdict(list)
        self.claims: dict[str, dict[str, Claim]] = defaultdict(dict)
        self._condition = asyncio.Condition()
        self._lock = asyncio.Lock()

    async def create_replication(self, replication: Replication) -> Replication:
        async with self._lock:
            if replication.id in self.replications:
                raise ConflictError(replication.id)
            self.replications[replication.id] = replication.model_copy(deep=True)
            return replication

    async def get_replication(self, replication_id: str) -> Replication | None:
        item = self.replications.get(replication_id)
        return item.model_copy(deep=True) if item else None

    async def transition(
        self, replication_id: str, expected: set[ReplicationStatus], target: ReplicationStatus
    ) -> Replication:
        async with self._lock:
            item = self.replications[replication_id]
            if item.status not in expected:
                raise ConflictError(f"expected {expected}, found {item.status}")
            item.status = target
            item.updated_at = utcnow()
            return item.model_copy(deep=True)

    async def set_paper_metadata(
        self, replication_id: str, *, title: str, authors: list[str], pdf_uri: str
    ) -> Replication:
        async with self._lock:
            item = self.replications[replication_id]
            item.title = title
            item.authors = authors
            item.pdf_gcs_uri = pdf_uri
            item.updated_at = utcnow()
            return item.model_copy(deep=True)

    async def put_claims(self, replication_id: str, claims: list[Claim]) -> None:
        async with self._lock:
            self.claims[replication_id] = {claim.id: claim.model_copy(deep=True) for claim in claims}

    async def list_claims(self, replication_id: str) -> list[Claim]:
        return [claim.model_copy(deep=True) for claim in self.claims[replication_id].values()]

    async def claim_event(self, event_id: str) -> bool:
        async with self._lock:
            if event_id in self.processed_events:
                return False
            self.processed_events.add(event_id)
            return True

    async def append_event(self, event: Event) -> Event:
        async with self._condition:
            stream = self.events[event.replication_id]
            event.sequence = len(stream) + 1
            stream.append(event)
            self._condition.notify_all()
            return event

    async def stream_events(self, replication_id: str, after: int = 0) -> AsyncIterator[Event]:
        cursor = after
        while True:
            available = self.events.get(replication_id, [])
            while cursor < len(available):
                event = available[cursor]
                cursor += 1
                yield event
            async with self._condition:
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=15)
                except TimeoutError:
                    yield Event(
                        sequence=cursor,
                        replication_id=replication_id,
                        kind="heartbeat",
                        stage="system",
                        message="connected",
                    )


state = InMemoryState()
