from fastapi.testclient import TestClient

from services.api.main import app


def test_calibration_runs_end_to_end_from_artifact_to_report() -> None:
    with TestClient(app) as client:
        response = client.post("/demo/calibration")
        assert response.status_code == 201
        run = response.json()
        assert run["status"] == "reported"
        assert run["summary_verdict"] == "1/1 calibration claims reproduced"
        claims = client.get(f"/replications/{run['id']}/claims").json()
        verdicts = client.get(f"/replications/{run['id']}/verdicts").json()
        assert len(claims) == len(verdicts) == 1
        assert verdicts[0]["status"] == "REPRODUCED"
        assert verdicts[0]["evidence_links"][0].endswith("metrics.json")
        report = client.get(f"/replications/{run['id']}/report")
        assert "REPRODUCED" in report.text
        assert "calibration" in report.text.lower()
