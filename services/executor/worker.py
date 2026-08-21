from __future__ import annotations

import asyncio
import os
import time

from packages.gcp.cloudbuild import BuildRequest
from packages.gcp.cloudrun_jobs import JobRequest
from packages.gcp.execution_api import GoogleExecutionApi
from packages.schemas.models import Attempt, Event, ReplicationStatus, WorkMessage, utcnow
from packages.science.budget import authorize_dispatch
from services.coder.bundle import build_source_bundle
from services.coder.generator import CodeGenerator, VertexCodeGenerator, package_generated_experiment


class ExecutorWorker:
    def __init__(self, state, bus, artifacts, generator: CodeGenerator | None = None,
        cloud: GoogleExecutionApi | None = None) -> None:
        self.state, self.bus, self.artifacts = state, bus, artifacts
        self.generator = generator or VertexCodeGenerator()
        self.cloud = cloud or GoogleExecutionApi()

    async def handle(self, message: WorkMessage) -> None:
        if not await self.state.claim_event(message.event_id):
            return
        replication = await self.state.get_replication(message.replication_id)
        plan = await self.state.get_plan(message.plan_id) if message.plan_id else None
        if replication is None or plan is None:
            raise ValueError("Unknown replication or plan")
        previous = await self.state.list_attempts(plan.id)
        decision = authorize_dispatch(replication.budget, replication.spent,
            completed_attempts=len(previous), estimated_minutes=plan.estimated_minutes,
            estimated_usd=plan.estimated_usd)
        if not decision.allowed:
            raise RuntimeError(f"Budget stopped execution: {decision.reason}")
        attempt = Attempt(plan_id=plan.id, n=len(previous) + 1, status="coding")
        await self.state.put_attempt(attempt)
        generated = await self.generator.generate(plan)
        source, digest = build_source_bundle(package_generated_experiment(generated))
        source_key = f"{replication.id}/attempts/{attempt.id}/source-{digest}.tar.gz"
        source_uri = self.artifacts.put_bytes(source_key, source, "application/gzip")
        attempt.code_gcs_uri = source_uri
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        region = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
        bucket = os.environ["ARTIFACT_BUCKET"]
        image = f"{region}-docker.pkg.dev/{project}/replicator/experiment:{attempt.id[:12]}"
        build = BuildRequest(project=project, region=region, source_bucket=bucket,
            source_object=source_key, image_uri=image,
            service_account=os.environ["BUILD_SERVICE_ACCOUNT"])
        await self.state.append_event(Event(replication_id=replication.id, kind="agent.decision",
            stage="coder", message="Generated immutable experiment source; Cloud Build started",
            detail={"attempt_id": attempt.id, "source_sha256": digest}))
        operation = await asyncio.to_thread(self.cloud.submit_build, build)
        await asyncio.to_thread(self.cloud.wait_build, operation,
            timeout_seconds=min(1200, int(replication.budget.max_job_minutes * 60)))
        await self.state.transition(replication.id, {ReplicationStatus.CODING}, ReplicationStatus.RUNNING)
        output_uri = f"gs://{bucket}/{replication.id}/attempts/{attempt.id}/out"
        request = JobRequest(project=project, region=region,
            job_name=f"rep-{replication.id[:8]}-{attempt.id[:8]}", image_uri=image,
            service_account=os.environ["RUNNER_SERVICE_ACCOUNT"], replication_id=replication.id,
            attempt_id=attempt.id, output_uri=output_uri,
            timeout_seconds=min(3600, int(plan.estimated_minutes * 60)))
        create_op = await asyncio.to_thread(self.cloud.create_job, request)
        await asyncio.to_thread(self.cloud.wait_operation, create_op, timeout_seconds=300)
        started = time.monotonic()
        run_op = await asyncio.to_thread(self.cloud.run_job, request)
        await asyncio.to_thread(self.cloud.wait_operation, run_op,
            timeout_seconds=request.timeout_seconds + 120)
        elapsed_minutes = (time.monotonic() - started) / 60
        metrics_uri = f"{output_uri}/metrics.json"
        self.artifacts.get_bytes(metrics_uri)
        attempt.status, attempt.exit_code = "succeeded", 0
        attempt.started_at, attempt.finished_at = utcnow(), utcnow()
        attempt.metrics_gcs_uri = metrics_uri
        attempt.job_name = request.job_name
        await self.state.put_attempt(attempt)
        await self.state.add_spend(replication.id, usd=plan.estimated_usd,
            job_minutes=elapsed_minutes)
        await self.state.transition(replication.id, {ReplicationStatus.RUNNING},
            ReplicationStatus.VERIFYING)
        await self.state.append_event(Event(replication_id=replication.id, kind="artifact",
            stage="executor", message="Cloud Run Job completed with a metrics artifact",
            detail={"attempt_id": attempt.id, "metrics_uri": metrics_uri}))
        await self.bus.publish("verify.requested", WorkMessage(event_type="verify.requested",
            replication_id=replication.id, plan_id=plan.id, attempt_id=attempt.id,
            trace_id=message.trace_id))
