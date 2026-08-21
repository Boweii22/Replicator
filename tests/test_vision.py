from packages.schemas.models import VisionAssessment
from services.verifier.vision import RUBRIC
from packages.schemas.models import Attempt, Claim, VerdictStatus
from services.verifier.verifier import verify_figure_claim


def test_visual_rubric_is_scientific_not_stylistic() -> None:
    assert "scientific conclusion" in RUBRIC and "stylistic similarity" in RUBRIC


def test_visual_assessment_requires_specific_evidence() -> None:
    assessment = VisionAssessment(same_trend=True, same_series_ordering=True,
        comparable_scale=True, same_scientific_conclusion=True,
        specific_evidence=["Both curves peak near the same labelled epoch"])
    assert assessment.same_scientific_conclusion
    claim = Claim(replication_id="rep", index=0, text="same curve", claim_type="figure",
        figure_gcs_uri="gs://evidence/paper.png", feasible=True)
    verdict = verify_figure_claim(claim, Attempt(plan_id="plan", n=1),
        "gs://evidence/ours.png", 0.9, assessment)
    assert verdict.status == VerdictStatus.REPRODUCED
    assert len(verdict.evidence_links) == 2
