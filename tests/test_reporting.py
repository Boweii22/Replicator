import io
import json

import pytest
from PIL import Image

from packages.schemas.models import Attempt, Claim, Replication, Verdict, VerdictStatus
from services.reporter.report import create_manifest, render_badge, render_report
from services.verifier.figures import figure_similarity
from services.verifier.metrics import EvidenceError, load_metrics_bytes
from services.verifier.verifier import evidence_contract_error, verify_numeric_claim


def fixture():
    replication = Replication(
        source_url="https://arxiv.org/abs/1706.03762", title="Evidence < Test"
    )
    claim = Claim(
        replication_id=replication.id,
        index=0,
        text="Accuracy > baseline",
        claim_type="metric",
        reported_value=90,
        unit="%",
        feasible=True,
    )
    attempt = Attempt(
        plan_id="plan",
        n=1,
        status="succeeded",
        metrics_gcs_uri="gs://evidence/metrics.json",
        stdout_gcs_uri="gs://evidence/stdout.log",
    )
    return replication, claim, attempt


def test_artifact_backed_verdict_report_and_signature() -> None:
    replication, claim, attempt = fixture()
    verdict = verify_numeric_claim(
        claim, attempt, load_metrics_bytes(json.dumps({claim.id: 92}).encode())
    )
    assert verdict.status == VerdictStatus.REPRODUCED
    report = render_report(replication, [claim], [verdict])
    assert "Evidence &lt; Test" in report and "REPRODUCED" in report
    manifest = create_manifest(replication.id, report.encode(), [verdict], b"test-key")
    assert len(manifest.report_sha256) == 64 and manifest.signature_algorithm == "HMAC-SHA256"


def test_verdict_refuses_missing_artifact() -> None:
    _, claim, attempt = fixture()
    attempt.metrics_gcs_uri = None
    with pytest.raises(ValueError, match="no metrics artifact"):
        verify_numeric_claim(claim, attempt, {claim.id: 90})


@pytest.mark.parametrize("payload", [b"not-json", b'{"claim": true}'])
def test_metrics_reject_invalid_evidence(payload: bytes) -> None:
    with pytest.raises(EvidenceError):
        load_metrics_bytes(payload)


def test_evidence_contract_rejects_impossible_bounded_metric() -> None:
    _, claim, _ = fixture()
    claim.metric_name = "classification_accuracy"
    claim.reported_value = 0.9
    claim.unit = None
    error = evidence_contract_error([claim], {claim.id: 1.519})
    assert error and "constrained to [0, 1]" in error


def test_evidence_contract_accepts_valid_bounded_metric() -> None:
    _, claim, _ = fixture()
    claim.metric_name = "classification_accuracy"
    claim.reported_value = 0.9
    claim.unit = None
    assert evidence_contract_error([claim], {claim.id: 0.92}) is None


def test_badge_counts() -> None:
    assert "3/4 claims reproduced" in render_badge(3, 4)


def test_identical_figures_have_perfect_sanity_score() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "#baff35").save(buffer, format="PNG")
    assert figure_similarity(buffer.getvalue(), buffer.getvalue()) == 1.0


def test_report_renders_interactive_figure_evidence() -> None:
    replication = Replication(source_url="https://arxiv.org/abs/1", title="Figures")
    claim = Claim(
        replication_id=replication.id,
        index=0,
        text="The curve rises",
        claim_type="figure",
        figure_gcs_uri=f"gs://bucket/{replication.id}/paper/figure.png",
    )
    verdict = Verdict(
        claim_id=claim.id,
        status=VerdictStatus.REPRODUCED,
        reasoning="Matched",
        evidence_links=[
            claim.figure_gcs_uri,
            f"gs://bucket/{replication.id}/attempts/one/out/figure.png",
        ],
    )
    report = render_report(replication, [claim], [verdict])
    assert "Overlay reproduced figure" in report
    assert 'class="ours"' in report
    assert "/artifact?uri=" in report
