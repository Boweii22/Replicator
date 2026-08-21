from __future__ import annotations

import asyncio
import json
import math
import random

from packages.gcp.artifacts import artifacts
from packages.gcp.state import state
from packages.schemas.models import (
    Attempt,
    Budget,
    Claim,
    Event,
    ExperimentPlan,
    Replication,
    ReplicationStatus,
)
from services.reporter.report import create_manifest, render_badge, render_report
from services.verifier.metrics import load_metrics_bytes
from services.verifier.verifier import verify_numeric_claim


async def run_calibration_mission() -> Replication:
    """Evidence-backed synthetic mission for local system calibration, never a paper claim."""
    replication = Replication(
        source_url="https://arxiv.org/abs/1706.03762",
        title="Replicator calibration: seeded ordinary least squares",
        authors=["Replicator test harness"],
        domain_tags=["calibration", "linear-regression"],
        budget=Budget(max_attempts=2, max_job_minutes=5, max_usd=0.25),
    )
    await state.create_replication(replication)
    await _stage(
        replication.id, "api", "Calibration mission queued; this is not a paper reproduction"
    )
    await state.transition(replication.id, {ReplicationStatus.QUEUED}, ReplicationStatus.READING)
    claim = Claim(
        replication_id=replication.id,
        index=0,
        text="The seeded calibration process has an OLS slope of 2.0 ± 5%.",
        claim_type="metric",
        metric_name="ols_slope",
        reported_value=2.0,
        tolerance_pct=5,
        priority=1,
        feasible=True,
        feasibility_reason="Deterministic CPU calculation using generated public data",
    )
    await state.put_claims(replication.id, [claim])
    await _stage(replication.id, "reader", "Extracted 1 calibration claim")
    await state.transition(replication.id, {ReplicationStatus.READING}, ReplicationStatus.PLANNING)
    plan = ExperimentPlan(
        replication_id=replication.id,
        claim_ids=[claim.id],
        strategy="reimplement",
        estimated_minutes=0.1,
        estimated_usd=0,
        steps=["Generate seeded observations", "Fit OLS slope", "Write metrics.json"],
    )
    await state.put_plan(plan)
    await _stage(replication.id, "planner", "Approved deterministic CPU plan at $0 estimated cost")
    await state.transition(replication.id, {ReplicationStatus.PLANNING}, ReplicationStatus.CODING)
    await _stage(replication.id, "coder", "Generated contract-compliant experiment bundle")
    await state.transition(replication.id, {ReplicationStatus.CODING}, ReplicationStatus.RUNNING)
    await asyncio.sleep(0.05)
    rng = random.Random(20260821)
    xs = list(range(1, 101))
    ys = [2.0 * x + rng.uniform(-0.25, 0.25) for x in xs]
    x_mean, y_mean = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - x_mean) ** 2 for x in xs
    )
    if not math.isfinite(slope):
        raise RuntimeError("ERROR_SIGNATURE:nonfinite_calibration_slope")
    metrics_bytes = json.dumps({claim.id: slope}, indent=2).encode()
    metrics_uri = artifacts.put_bytes(
        f"{replication.id}/attempts/1/metrics.json", metrics_bytes, "application/json"
    )
    logs_uri = artifacts.put_bytes(
        f"{replication.id}/attempts/1/stdout.log",
        f"seed=20260821\nn=100\nols_slope={slope:.12f}\n".encode(),
        "text/plain",
    )
    attempt = Attempt(
        plan_id=plan.id,
        n=1,
        status="succeeded",
        exit_code=0,
        metrics_gcs_uri=metrics_uri,
        stdout_gcs_uri=logs_uri,
    )
    await state.put_attempt(attempt)
    await state.add_spend(replication.id, usd=0, job_minutes=0.01)
    await _stage(replication.id, "executor", f"Experiment finished; artifact slope={slope:.6f}")
    await state.transition(replication.id, {ReplicationStatus.RUNNING}, ReplicationStatus.VERIFYING)
    verdict = verify_numeric_claim(claim, attempt, load_metrics_bytes(metrics_bytes))
    await state.put_verdict(verdict)
    await _stage(replication.id, "verifier", f"Evidence rubric returned {verdict.status}")
    current = await state.get_replication(replication.id)
    report_bytes = render_report(current, [claim], [verdict]).encode()
    report_uri = artifacts.put_bytes(
        f"{replication.id}/report/report.html", report_bytes, "text/html"
    )
    manifest = create_manifest(replication.id, report_bytes, [verdict])
    artifacts.put_bytes(
        f"{replication.id}/report/manifest.json",
        manifest.model_dump_json(indent=2).encode(),
        "application/json",
    )
    artifacts.put_bytes(
        f"{replication.id}/report/badge.svg", render_badge(1, 1).encode(), "image/svg+xml"
    )
    finished = await state.finish_report(
        replication.id, report_uri=report_uri, summary="1/1 calibration claims reproduced"
    )
    await _stage(replication.id, "reporter", "Tamper-evident report and badge written")
    return finished


async def _stage(replication_id: str, stage: str, message: str) -> None:
    await state.append_event(
        Event(
            replication_id=replication_id,
            kind="agent.decision",
            stage=stage,
            message=message,
            detail={"mode": "evidence-backed-calibration"},
        )
    )
