from __future__ import annotations

from packages.schemas.models import Event, ReplicationStatus, Verdict, VerdictStatus, WorkMessage
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
        feasible = [claim for claim in claims if claim.feasible]
        if not feasible:
            await self._stop_with_verdicts(
                replication,
                claims,
                message,
                "No claim is feasible within the declared data and compute constraints.",
            )
            return
        official_repo = await self.discovery.find_official_repo(replication.title or "")
        try:
            plan = await self.generator.create(replication, claims, official_repo)
        except ValueError as exc:
            await self._stop_with_verdicts(replication, claims, message, str(exc))
            return
        await self.state.put_plan(plan)
        await self.state.transition(
            replication.id, {ReplicationStatus.PLANNING}, ReplicationStatus.CODING
        )
        await self.state.append_event(
            Event(
                replication_id=replication.id,
                kind="agent.decision",
                stage="planner",
                message=f"Selected {plan.strategy} plan for {len(plan.claim_ids)} feasible claims",
                detail={
                    "plan_id": plan.id,
                    "estimated_minutes": plan.estimated_minutes,
                    "estimated_usd": plan.estimated_usd,
                },
            )
        )
        await self.bus.publish(
            "job.dispatch",
            WorkMessage(
                event_type="code.requested",
                replication_id=replication.id,
                plan_id=plan.id,
                trace_id=message.trace_id,
            ),
        )

    async def _stop_with_verdicts(self, replication, claims, message, reason: str) -> None:
        for claim in claims:
            claim_reason = claim.feasibility_reason if not claim.feasible else reason
            await self.state.put_verdict(
                Verdict(
                    claim_id=claim.id,
                    status=VerdictStatus.NOT_ATTEMPTED,
                    reasoning=claim_reason or reason,
                )
            )
        await self.state.append_event(
            Event(
                replication_id=replication.id,
                kind="agent.decision",
                stage="planner",
                message="Execution stopped honestly before dispatch",
                detail={"reason": reason, "verdict": VerdictStatus.NOT_ATTEMPTED.value},
            )
        )
        await self.state.transition(
            replication.id, {ReplicationStatus.PLANNING}, ReplicationStatus.VERIFYING
        )
        await self.bus.publish(
            "report.ready",
            WorkMessage(
                event_type="report.ready",
                replication_id=replication.id,
                trace_id=message.trace_id,
            ),
        )
