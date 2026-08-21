from __future__ import annotations

from packages.schemas.models import Budget, Claim, ExperimentPlan


def build_plan(
    replication_id: str,
    claims: list[Claim],
    budget: Budget,
    *,
    official_repo: str | None,
) -> ExperimentPlan:
    feasible = [claim for claim in claims if claim.feasible]
    if not feasible:
        raise ValueError("No feasible quantitative claims")
    strategy = "official_repo" if official_repo else "reimplement"
    minutes = min(budget.max_job_minutes, max(5.0, len(feasible) * 4.0))
    estimated_usd = round(minutes * 0.02, 2)
    if estimated_usd > budget.max_usd:
        raise ValueError("Estimated experiment exceeds cost cap")
    metric_keys = ", ".join(claim.id for claim in feasible)
    return ExperimentPlan(
        replication_id=replication_id,
        claim_ids=[claim.id for claim in feasible],
        strategy=strategy,
        repo_url=official_repo,
        estimated_minutes=minutes,
        estimated_usd=estimated_usd,
        steps=[
            "Resolve and pin all dependencies",
            "Acquire only public datasets with recorded checksums",
            "Run the smallest faithful configuration within the budget",
            f"Write /out/metrics.json with claim IDs: {metric_keys}",
            "Write claim figures beneath /out/figures and emit provenance.json",
        ],
        risks=[] if official_repo else ["No verified official implementation was found"],
    )
