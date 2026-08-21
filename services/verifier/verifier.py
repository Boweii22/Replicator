from packages.schemas.models import Attempt, Claim, Verdict, VerdictStatus, VisionAssessment
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


def verify_figure_claim(claim: Claim, attempt: Attempt, reproduced_uri: str,
    similarity: float, assessment: VisionAssessment) -> Verdict:
    if not claim.figure_gcs_uri:
        raise ValueError("Figure claim has no paper figure artifact")
    if assessment.same_scientific_conclusion and assessment.same_trend \
        and assessment.same_series_ordering and assessment.comparable_scale:
        status = VerdictStatus.REPRODUCED
    elif assessment.same_scientific_conclusion:
        status = VerdictStatus.PARTIAL
    else:
        status = VerdictStatus.FAILED
    evidence = "; ".join(assessment.specific_evidence)
    caveats = "; ".join(assessment.caveats) or "none"
    return Verdict(claim_id=claim.id, attempt_id=attempt.id, status=status,
        figure_similarity_score=similarity,
        vision_assessment=f"Evidence: {evidence}. Caveats: {caveats}.",
        reasoning=("Gemini vision applied the declared trend/order/scale/conclusion rubric; "
            f"pixel sanity score={similarity:.4f}."),
        evidence_links=[claim.figure_gcs_uri, reproduced_uri])
