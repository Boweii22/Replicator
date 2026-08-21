from packages.schemas.models import VisionAssessment
from services.verifier.vision import RUBRIC


def test_visual_rubric_is_scientific_not_stylistic() -> None:
    assert "scientific conclusion" in RUBRIC and "stylistic similarity" in RUBRIC


def test_visual_assessment_requires_specific_evidence() -> None:
    assessment = VisionAssessment(same_trend=True, same_series_ordering=True,
        comparable_scale=True, same_scientific_conclusion=True,
        specific_evidence=["Both curves peak near the same labelled epoch"])
    assert assessment.same_scientific_conclusion
