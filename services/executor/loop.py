from __future__ import annotations

from typing import Protocol

from packages.gcp.state import InMemoryState
from packages.schemas.models import Attempt, ExecutionResult, Memory, ReplicationStatus, utcnow
from packages.science.budget import authorize_dispatch
from services.executor.healing import extract_error_signature, memory_key


class JobRunner(Protocol):
    async def run(self, attempt: Attempt) -> ExecutionResult: ...


class Repairer(Protocol):
    async def repair(self, attempt: Attempt, signature: str, lesson: str | None) -> Attempt: ...


async def execute_with_healing(
    state: InMemoryState,
    replication_id: str,
    plan_id: str,
    runner: JobRunner,
    repairer: Repairer,
) -> Attempt:
    replication = await state.get_replication(replication_id)
    plan = await state.get_plan(plan_id)
    if replication is None or plan is None:
        raise ValueError("Replication or plan not found")
    await state.transition(replication_id, {ReplicationStatus.CODING}, ReplicationStatus.RUNNING)
    while True:
        previous = await state.list_attempts(plan_id)
        decision = authorize_dispatch(
            replication.budget,
            replication.spent,
            completed_attempts=len(previous),
            estimated_minutes=plan.estimated_minutes,
            estimated_usd=plan.estimated_usd,
        )
        if not decision.allowed:
            raise RuntimeError(f"Budget stopped execution: {decision.reason}")
        attempt = Attempt(
            plan_id=plan_id, n=len(previous) + 1, status="running", started_at=utcnow()
        )
        await state.put_attempt(attempt)
        result = await runner.run(attempt)
        attempt.exit_code = result.exit_code
        attempt.finished_at = utcnow()
        attempt.stdout_gcs_uri = result.stdout_uri
        attempt.metrics_gcs_uri = result.metrics_uri
        attempt.figures_gcs_uri = result.figure_uris
        attempt.status = "succeeded" if result.exit_code == 0 else "failed"
        await state.add_spend(replication_id, usd=result.cost_usd, job_minutes=result.job_minutes)
        await state.put_attempt(attempt)
        replication = await state.get_replication(replication_id)
        if result.exit_code == 0:
            return attempt
        signature = extract_error_signature(result.stderr_tail)
        attempt.error_signature = signature
        key = memory_key("experiment", signature)
        known = await state.get_memory(key)
        repaired = await repairer.repair(attempt, signature, known.lesson if known else None)
        await state.put_attempt(repaired)
        if repaired.patch_summary:
            await state.put_memory(
                Memory(
                    key=key,
                    lesson=repaired.diagnosis or repaired.patch_summary,
                    fix_snippet=repaired.patch_summary,
                    origin_replication_id=replication_id,
                )
            )
