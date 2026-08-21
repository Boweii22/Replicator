import asyncio
import json
from pathlib import Path
from uuid import uuid4

from packages.gcp.artifacts import ArtifactStore
from packages.gcp.pubsub import LocalEventBus
from packages.gcp.state import InMemoryState
from packages.schemas.models import Attempt, Claim, Replication, ReplicationStatus, WorkMessage
from services.reporter.worker import ReporterWorker
from services.verifier.worker import VerifierWorker


def test_verifier_to_reporter_produces_artifact_backed_report() -> None:
    asyncio.run(_scenario())


async def _scenario() -> None:
    state, bus = InMemoryState(), LocalEventBus()
    store = ArtifactStore(local_root=Path(".test-artifacts") / uuid4().hex)
    replication = Replication(source_url="https://arxiv.org/abs/1706.03762",
        title="Worker chain", status=ReplicationStatus.VERIFYING)
    await state.create_replication(replication)
    claim = Claim(replication_id=replication.id, index=0, text="Score is 10",
        claim_type="metric", reported_value=10, feasible=True)
    await state.put_claims(replication.id, [claim])
    metrics_uri = store.put_bytes(f"{replication.id}/metrics.json",
        json.dumps({claim.id: 10.1}).encode(), "application/json")
    attempt = Attempt(plan_id="plan", n=1, status="succeeded", metrics_gcs_uri=metrics_uri)
    await state.put_attempt(attempt)
    reporter = ReporterWorker(state, store)
    bus.subscribe("report.ready", reporter.handle)
    verifier = VerifierWorker(state, bus, store)
    await verifier.handle(WorkMessage(event_type="verify.requested",
        replication_id=replication.id, attempt_id=attempt.id))
    await bus.drain()
    finished = await state.get_replication(replication.id)
    assert finished.status == ReplicationStatus.REPORTED
    assert finished.report_gcs_uri.endswith("report.html")
    assert (await state.list_verdicts(replication.id))[0].status == "REPRODUCED"
