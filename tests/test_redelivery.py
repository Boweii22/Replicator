import asyncio

from packages.gcp.state import InMemoryState


def test_failed_event_can_be_reclaimed_but_completed_event_cannot() -> None:
    asyncio.run(_scenario())


async def _scenario() -> None:
    state = InMemoryState()
    assert await state.claim_event("event")
    assert not await state.claim_event("event")
    await state.release_event("event")
    assert await state.claim_event("event")
