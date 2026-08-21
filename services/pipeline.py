from __future__ import annotations

from packages.gcp.pubsub import bus
from packages.gcp.state import ConflictError, state
from packages.schemas.models import Event, ReplicationStatus, WorkMessage
from packages.telemetry import replication_span

_registered = False


async def reader(message: WorkMessage) -> None:
    """Credential-free local contract transition; cloud deploy uses ReaderWorker."""
    if not await state.claim_event(message.event_id):
        return
    with replication_span("reader", replication_id=message.replication_id, model="gemini-3.5-flash"):
        try:
            await state.transition(
                message.replication_id, {ReplicationStatus.QUEUED}, ReplicationStatus.READING
            )
        except ConflictError:
            return
        await state.append_event(Event(
            replication_id=message.replication_id,
            kind="agent.decision",
            stage="reader",
            message="Paper ingestion claimed idempotently; extraction is ready for the ADK worker",
            detail={"trace_id": message.trace_id, "mode": "local-contract"},
        ))


def register_local_pipeline() -> None:
    global _registered
    if not _registered:
        bus.subscribe("replication.requested", reader)
        _registered = True
