import json
import io

import pytest
from PIL import Image

from packages.schemas.models import Attempt, Claim, Replication, VerdictStatus
from services.reporter.report import create_manifest, render_badge, render_report
from services.verifier.metrics import EvidenceError, load_metrics_bytes
from services.verifier.verifier import verify_numeric_claim
from services.verifier.figures import figure_similarity


def fixture():
    replication = Replication(source_url="https://arxiv.org/abs/1706.03762", title="Evidence < Test")
    claim = Claim(replication_id=replication.id, index=0, text="Accuracy > baseline",
        claim_type="metric", reported_value=90, unit="%", feasible=True)
    attempt = Attempt(plan_id="plan", n=1, status="succeeded",
        metrics_gcs_uri="gs://evidence/metrics.json", stdout_gcs_uri="gs://evidence/stdout.log")
    return replication, claim, attempt


def test_artifact_backed_verdict_report_and_signature() -> None:
    replication, claim, attempt = fixture()
    verdict = verify_numeric_claim(claim, attempt, load_metrics_bytes(json.dumps({claim.id: 92}).encode()))
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


def test_badge_counts() -> None:
    assert "3/4 claims reproduced" in render_badge(3, 4)


def test_identical_figures_have_perfect_sanity_score() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "#baff35").save(buffer, format="PNG")
    assert figure_similarity(buffer.getvalue(), buffer.getvalue()) == 1.0
