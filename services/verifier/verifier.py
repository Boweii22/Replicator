from packages.schemas.models import Attempt, Claim, Verdict, VerdictStatus
from packages.science import numeric_verdict


def verify_numeric_claim(claim: Claim, attempt: Attempt, metrics: dict[str, float]) -> Verdict:
    if not attempt.metrics_gcs_uri:
        raise ValueError("Evidence policy violation: attempt has no metrics artifact URI")
    links = [attempt.metrics_gcs_uri] + ([attempt.stdout_gcs_uri] if attempt.stdout_gcs_uri else [])
    if claim.reported_value is None:
        return Verdict(claim_id=claim.id, attempt_id=attempt.id,
            status=VerdictStatus.NOT_ATTEMPTED,
            reasoning="The paper claim has no machine-readable reported value.", evidence_links=links)
    if claim.id not in metrics:
        return Verdict(claim_id=claim.id, attempt_id=attempt.id, status=VerdictStatus.FAILED,
            reasoning="The successful job artifact did not contain this claim ID.", evidence_links=links)
    obtained = metrics[claim.id]
    status, delta = numeric_verdict(claim.reported_value, obtained, claim.tolerance_pct)
    return Verdict(claim_id=claim.id, attempt_id=attempt.id, status=status,
        obtained_value=obtained, delta_pct=round(delta, 6),
        reasoning=f"Paper: {claim.reported_value:g}{claim.unit or ''}; artifact: {obtained:g}{claim.unit or ''}; delta {delta:.3f}% vs {claim.tolerance_pct:g}% tolerance.",
        evidence_links=links)
