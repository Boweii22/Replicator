from __future__ import annotations

from packages.schemas.models import Event, ReplicationStatus, WorkMessage
from services.planner.discovery import RepositoryDiscovery
from services.planner.generator import VertexPlanGenerator


class PlannerWorker:
    def __init__(self, state, bus, discovery=None, generator=None) -> None:
        self.state = state
        self.bus = bus
        self.discovery = discovery or RepositoryDiscovery()
        self.generator = generator or VertexPlanGenerator()

    async def handle(self, message: WorkMessage) -> None:
        if not await self.state.claim_event(message.event_id):
            return
        replication = await self.state.get_replication(message.replication_id)
        if replication is None:
            raise ValueError("Unknown replication")
        claims = await self.state.list_claims(replication.id)
        official_repo = await self.discovery.find_official_repo(replication.title or "")
        plan = await self.generator.create(replication, claims, official_repo)
        await self.state.put_plan(plan)
        await self.state.transition(
            replication.id, {ReplicationStatus.PLANNING}, ReplicationStatus.CODING
        )
        await self.state.append_event(Event(replication_id=replication.id,
            kind="agent.decision", stage="planner",
            message=f"Selected {plan.strategy} plan for {len(plan.claim_ids)} feasible claims",
            detail={"plan_id": plan.id, "estimated_minutes": plan.estimated_minutes,
                "estimated_usd": plan.estimated_usd}))
        await self.bus.publish("job.dispatch", WorkMessage(event_type="code.requested",
            replication_id=replication.id, plan_id=plan.id, trace_id=message.trace_id))
