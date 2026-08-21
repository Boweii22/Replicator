import asyncio

from packages.gcp.pubsub import LocalEventBus
from packages.gcp.state import InMemoryState
from packages.schemas.models import Budget, Claim, Replication, ReplicationStatus, WorkMessage
from services.planner.worker import PlannerWorker


def test_planner_worker_persists_plan_and_emits_ids_only() -> None:
    asyncio.run(_scenario())


async def _scenario() -> None:
    state, bus = InMemoryState(), LocalEventBus()
    replication = Replication(source_url="https://arxiv.org/abs/1706.03762",
        status=ReplicationStatus.PLANNING, budget=Budget(max_job_minutes=20, max_usd=1))
    await state.create_replication(replication)
    claim = Claim(replication_id=replication.id, index=0, text="Accuracy is 90%",
        claim_type="metric", reported_value=90, feasible=True)
    await state.put_claims(replication.id, [claim])
    received = []
    bus.subscribe("job.dispatch", lambda message: _record(received, message))
    message = WorkMessage(event_type="plan.ready", replication_id=replication.id)
    worker = PlannerWorker(state, bus, Discovery(), Generator())
    await worker.handle(message)
    await bus.drain()
    updated = await state.get_replication(replication.id)
    assert updated.status == ReplicationStatus.CODING
    assert received[0].plan_id and received[0].replication_id == replication.id
    await worker.handle(message)
    assert len(received) == 1


async def _record(target: list, message: WorkMessage) -> None:
    target.append(message)


class Discovery:
    async def find_official_repo(self, title: str):
        return "https://github.com/example/official"


class Generator:
    async def create(self, replication, claims, official_repo):
        from services.planner.planner import build_plan
        return build_plan(replication.id, claims, replication.budget, official_repo=official_repo)
