import asyncio
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from packages.gcp.artifacts import ArtifactStore
from packages.gcp.pubsub import LocalEventBus
from packages.gcp.state import InMemoryState
from packages.schemas.models import (
    Budget,
    Claim,
    ExperimentPlan,
    GeneratedExperiment,
    Replication,
    ReplicationStatus,
    WorkMessage,
)
from services.executor.worker import ExecutorWorker


class Generator:
    async def generate(self, plan):
        return GeneratedExperiment(run_py="print('compute')", requirements_txt="",
            rationale="test generation")


class BrokenCloud:
    def submit_build(self, request):
        raise RuntimeError("ERROR_SIGNATURE:dependency-conflict")


class Repairer:
    async def repair(self, attempt, signature, lesson):
        attempt.diagnosis = "Dependency versions conflict"
        attempt.patch_summary = "Pin dependency==1.0"
        return attempt


def test_executor_retries_then_reports_honest_failure_at_cap() -> None:
    with patch.dict(os.environ, {
        "GOOGLE_CLOUD_PROJECT": "project", "GOOGLE_CLOUD_LOCATION": "europe-west1",
        "ARTIFACT_BUCKET": "unused", "BUILD_SERVICE_ACCOUNT": "builder@example",
        "RUNNER_SERVICE_ACCOUNT": "runner@example",
    }):
        asyncio.run(_scenario())


async def _scenario() -> None:
    state, bus = InMemoryState(), LocalEventBus()
    replication = Replication(source_url="https://arxiv.org/abs/1706.03762",
        status=ReplicationStatus.CODING,
        budget=Budget(max_attempts=2, max_job_minutes=20, max_usd=1))
    await state.create_replication(replication)
    claim = Claim(replication_id=replication.id, index=0, text="Score is 1",
        claim_type="metric", reported_value=1, feasible=True)
    await state.put_claims(replication.id, [claim])
    plan = ExperimentPlan(replication_id=replication.id, claim_ids=[claim.id],
        strategy="reimplement", estimated_minutes=1, estimated_usd=0.1, steps=["run"])
    await state.put_plan(plan)
    reports = []
    bus.subscribe("report.ready", lambda message: _record(reports, message))
    store = ArtifactStore(local_root=Path(".test-artifacts") / uuid4().hex)
    store.bucket = None
    worker = ExecutorWorker(state, bus, store, Generator(), BrokenCloud(), Repairer())
    first = WorkMessage(event_type="code.requested", replication_id=replication.id, plan_id=plan.id)
    try:
        await worker.handle(first)
        raise AssertionError("first failure should request redelivery")
    except RuntimeError:
        await state.release_event(first.event_id)
    await worker.handle(first)
    await bus.drain()
    assert len(await state.list_attempts(plan.id)) == 2
    assert len(state.memories) == 1
    assert (await state.list_verdicts(replication.id))[0].status == "FAILED"
    assert len(reports) == 1


async def _record(target, message):
    target.append(message)
