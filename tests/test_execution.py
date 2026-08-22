import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from packages.gcp.state import InMemoryState
from packages.schemas.models import (
    Attempt,
    Budget,
    ExecutionResult,
    ExperimentPlan,
    Replication,
    ReplicationStatus,
    Spend,
)
from packages.science.budget import authorize_dispatch
from runner.replicator_contract import ContractViolation, validate_outputs
from services.executor.healing import extract_error_signature, memory_key
from services.executor.loop import execute_with_healing


def test_budget_guard_checks_projected_spend() -> None:
    decision = authorize_dispatch(
        Budget(max_attempts=3, max_job_minutes=20, max_usd=1),
        Spend(usd=0.8, job_minutes=8),
        completed_attempts=1,
        estimated_minutes=5,
        estimated_usd=0.3,
    )
    assert not decision.allowed
    assert decision.reason == "cost cap exceeded"


def output_dir() -> Path:
    target = Path(".test-artifacts") / uuid4().hex
    target.mkdir(parents=True)
    return target


def test_runner_contract_accepts_only_exact_finite_claims() -> None:
    target = output_dir()
    (target / "metrics.json").write_text(json.dumps({"claim-a": 0.91}), encoding="utf-8")
    assert validate_outputs(target, {"claim-a"}) == {"claim-a": 0.91}


def test_runner_contract_rejects_missing_claim() -> None:
    target = output_dir()
    (target / "metrics.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ContractViolation, match="missing_claims"):
        validate_outputs(target, {"claim-a"})


def test_error_signature_and_memory_key_are_stable() -> None:
    assert (
        extract_error_signature("boom\nERROR_SIGNATURE:cuda-out-of-memory\n")
        == "cuda-out-of-memory"
    )
    assert memory_key("Torch", "cuda-out-of-memory") == memory_key("torch", "cuda-out-of-memory")


@pytest.mark.parametrize(
    "stderr",
    [
        "urllib.error.HTTPError: HTTP Error 404: Not Found",
        "ValueError: Invalid dataset name =Fruit is not available",
        "BadZipFile: File is not a zip file",
        "RuntimeError: All download strategies failed after 1 retries each",
    ],
)
def test_dataset_failures_share_one_actionable_signature(stderr: str) -> None:
    assert extract_error_signature(stderr) == "dataset-source-unavailable"


class FailThenPassRunner:
    calls = 0

    async def run(self, attempt: Attempt) -> ExecutionResult:
        self.calls += 1
        if self.calls == 1:
            return ExecutionResult(
                exit_code=1,
                job_minutes=1,
                cost_usd=0.05,
                stdout_uri="gs://evidence/attempt-1.log",
                stderr_tail="ERROR_SIGNATURE:dependency-version-conflict",
            )
        return ExecutionResult(
            exit_code=0,
            job_minutes=1,
            cost_usd=0.05,
            stdout_uri="gs://evidence/attempt-2.log",
            metrics_uri="gs://evidence/metrics.json",
        )


class RecordingRepairer:
    async def repair(self, attempt: Attempt, signature: str, lesson: str | None) -> Attempt:
        attempt.diagnosis = f"Pinned the incompatible dependency ({signature})"
        attempt.patch_summary = "Pinned library==1.2.3"
        return attempt


def test_executor_heals_failure_and_records_memory() -> None:
    asyncio.run(run_healing_scenario())


async def run_healing_scenario() -> None:
    state = InMemoryState()
    replication = Replication(
        source_url="https://arxiv.org/abs/1706.03762",
        status=ReplicationStatus.CODING,
        budget=Budget(max_attempts=3, max_job_minutes=20, max_usd=1),
    )
    await state.create_replication(replication)
    plan = ExperimentPlan(
        replication_id=replication.id,
        claim_ids=["claim-a"],
        strategy="reimplement",
        estimated_minutes=2,
        estimated_usd=0.1,
        steps=["run"],
    )
    await state.put_plan(plan)
    result = await execute_with_healing(
        state, replication.id, plan.id, FailThenPassRunner(), RecordingRepairer()
    )
    assert result.status == "succeeded"
    assert result.n == 2
    assert len(await state.list_attempts(plan.id)) == 2
    assert len(state.memories) == 1
