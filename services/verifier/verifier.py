import re

from packages.schemas.models import Attempt, Claim, Verdict, VerdictStatus, VisionAssessment
from packages.science import numeric_verdict
from services.verifier.metrics import Measurement


BOUNDED_METRIC_WORDS = ("accuracy", "precision", "recall", "f1", "auc", "proportion")
OPENML_DATASET_NAMES = {
    "40996": "fashionmnist",
    "40979": "mfeatpixel",
    "46783": "coil20",
}


def _measurement(item: Measurement | float) -> Measurement:
    return item if isinstance(item, Measurement) else Measurement(value=float(item), legacy=True)


def evidence_contract_error(claims: list[Claim], metrics: dict[str, Measurement | float]) -> str | None:
    """Reject the complete artifact when one value proves claim/metric misbinding."""
    for claim in claims:
        if claim.id not in metrics or claim.reported_value is None:
            continue
        label = f"{claim.metric_name or ''} {claim.text}".lower()
        value = _measurement(metrics[claim.id]).value
        reported_on_unit_scale = 0 <= claim.reported_value <= 1 and claim.unit != "%"
        if reported_on_unit_scale and any(word in label for word in BOUNDED_METRIC_WORDS):
            if not 0 <= value <= 1:
                return (
                    f"Claim {claim.id} received {value:g} for a metric constrained to [0, 1]. "
                    "This proves the artifact's claim-to-measurement mapping is unsafe."
                )
    return None


def verify_numeric_claim(
    claim: Claim, attempt: Attempt, metrics: dict[str, Measurement | float]
) -> Verdict:
    if not attempt.metrics_gcs_uri:
        raise ValueError("Evidence policy violation: attempt has no metrics artifact URI")
    links = [attempt.metrics_gcs_uri] + ([attempt.stdout_gcs_uri] if attempt.stdout_gcs_uri else [])
    if claim.reported_value is None:
        return Verdict(
            claim_id=claim.id,
            attempt_id=attempt.id,
            status=VerdictStatus.NOT_ATTEMPTED,
            reasoning="The paper claim has no machine-readable reported value.",
            evidence_links=links,
        )
    if claim.id not in metrics:
        return Verdict(
            claim_id=claim.id,
            attempt_id=attempt.id,
            status=VerdictStatus.NOT_ATTEMPTED,
            reasoning=(
                "The job completed, but no faithful measurement was available for this claim. "
                "Absence of a metric is not evidence against the paper."
            ),
            evidence_links=links,
        )
    measurement = _measurement(metrics[claim.id])
    obtained = measurement.value
    semantic_error = measurement_semantic_error(claim, measurement)
    if semantic_error:
        return Verdict(
            claim_id=claim.id,
            attempt_id=attempt.id,
            status=VerdictStatus.NOT_ATTEMPTED,
            reasoning=f"Measurement was not comparable to this claim: {semantic_error}",
            evidence_links=links,
        )
    status, delta = numeric_verdict(claim.reported_value, obtained, claim.tolerance_pct)
    return Verdict(
        claim_id=claim.id,
        attempt_id=attempt.id,
        status=status,
        obtained_value=obtained,
        delta_pct=round(delta, 6),
        reasoning=f"Paper: {claim.reported_value:g}{claim.unit or ''}; artifact: {obtained:g}{claim.unit or ''}; delta {delta:.3f}% vs {claim.tolerance_pct:g}% tolerance.",
        evidence_links=links,
    )


def _normal(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def measurement_semantic_error(claim: Claim, measurement: Measurement) -> str | None:
    if measurement.legacy:
        return None
    if claim.metric_name and _normal(claim.metric_name) != _normal(measurement.metric_name):
        return f"metric {measurement.metric_name!r} does not match {claim.metric_name!r}"
    if _normal(claim.unit) != _normal(measurement.unit):
        return f"unit {measurement.unit!r} does not match {claim.unit or ''!r}"
    openml_match = re.search(r"openml\.org/(?:d/|data/)?(\d+)", measurement.data_source.lower())
    if openml_match and openml_match.group(1) in OPENML_DATASET_NAMES:
        canonical = OPENML_DATASET_NAMES[openml_match.group(1)]
        declared = {_normal(name) for name in measurement.dataset_names}
        if canonical not in declared:
            return (
                f"OpenML dataset {openml_match.group(1)} is {canonical!r}, but the artifact "
                f"declares {measurement.dataset_names!r}"
            )
    text = claim.text.lower()
    count_match = re.search(r"(?:all(?:\s+of)?|over)\s+(\d+)\s+(?:ucr\s+)?datasets", text)
    if count_match and measurement.dataset_count < int(count_match.group(1)):
        return (
            f"claim requires {count_match.group(1)} datasets; artifact declares "
            f"{measurement.dataset_count}"
        )
    if "larger datasets" in text and _normal(measurement.data_source) in {"synthetic", "generated"}:
        return "a synthetic smoke benchmark cannot establish a claim about larger real datasets"
    dataset_match = re.search(r"\bon (?:the )?([a-z0-9-]+) dataset\b", text)
    if dataset_match:
        expected = _normal(dataset_match.group(1))
        actual = {_normal(name) for name in measurement.dataset_names}
        if expected not in actual:
            return f"claim requires dataset {dataset_match.group(1)!r}; artifact declares {measurement.dataset_names!r}"
    return None


def verify_figure_claim(
    claim: Claim,
    attempt: Attempt,
    reproduced_uri: str,
    similarity: float,
    assessment: VisionAssessment,
) -> Verdict:
    if not claim.figure_gcs_uri:
        raise ValueError("Figure claim has no paper figure artifact")
    if (
        assessment.same_scientific_conclusion
        and assessment.same_trend
        and assessment.same_series_ordering
        and assessment.comparable_scale
    ):
        status = VerdictStatus.REPRODUCED
    elif assessment.same_scientific_conclusion:
        status = VerdictStatus.PARTIAL
    else:
        status = VerdictStatus.FAILED
    evidence = "; ".join(assessment.specific_evidence)
    caveats = "; ".join(assessment.caveats) or "none"
    return Verdict(
        claim_id=claim.id,
        attempt_id=attempt.id,
        status=status,
        figure_similarity_score=similarity,
        vision_assessment=f"Evidence: {evidence}. Caveats: {caveats}.",
        reasoning=(
            "Gemini vision applied the declared trend/order/scale/conclusion rubric; "
            f"pixel sanity score={similarity:.4f}."
        ),
        evidence_links=[claim.figure_gcs_uri, reproduced_uri],
    )
