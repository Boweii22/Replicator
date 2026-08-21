import pytest

from packages.schemas.models import Budget, Claim, PlanProposal, Replication
from services.planner.generator import proposal_to_plan


def test_generated_plan_cannot_cross_code_enforced_budget() -> None:
    replication = Replication(source_url="https://arxiv.org/abs/1706.03762",
        budget=Budget(max_attempts=2, max_job_minutes=10, max_usd=0.5))
    claim = Claim(replication_id=replication.id, index=0, text="score", claim_type="metric",
        reported_value=1, feasible=True)
    proposal = PlanProposal(strategy="reimplement", estimated_minutes=11,
        estimated_usd=0.2, steps=["run"])
    with pytest.raises(ValueError, match="runtime cap"):
        proposal_to_plan(replication, [claim], proposal)
