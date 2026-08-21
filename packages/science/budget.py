from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.models import Budget, Spend


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str


def authorize_dispatch(
    budget: Budget,
    spent: Spend,
    *,
    completed_attempts: int,
    estimated_minutes: float,
    estimated_usd: float,
) -> BudgetDecision:
    checks = (
        (completed_attempts >= budget.max_attempts, "attempt cap reached"),
        (spent.job_minutes + estimated_minutes > budget.max_job_minutes, "runtime cap exceeded"),
        (spent.usd + estimated_usd > budget.max_usd, "cost cap exceeded"),
    )
    for blocked, reason in checks:
        if blocked:
            return BudgetDecision(False, reason)
    return BudgetDecision(True, "within enforced budget")
