from pathlib import Path

from fastapi.testclient import TestClient

from services.api.main import app


def test_mission_control_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Evidence, not vibes" in response.text


def test_mission_control_distinguishes_completed_noncomparable_run() -> None:
    script = (Path(__file__).parents[1] / "apps" / "web" / "app.js").read_text()
    assert "The experiment ran; no paper claims were comparable." in script
    assert "isNoComparableEvidence" in script


def test_evidence_policy_is_explained_without_failure_jargon() -> None:
    page = (Path(__file__).parents[1] / "apps" / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Strict evidence · no guessing" in page


def test_create_get_and_budget_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/replications",
            json={
                "source_url": "https://arxiv.org/abs/1706.03762",
                "budget": {"max_attempts": 2, "max_job_minutes": 10, "max_usd": 0.75},
            },
        )
        assert response.status_code == 202
        created = response.json()
        assert created["status"] == "queued"
        assert created["budget"]["max_attempts"] == 2
        fetched = client.get(f"/replications/{created['id']}")
        assert fetched.status_code == 200
        archive = client.get("/replications")
        assert archive.status_code == 200
        assert created["id"] in {item["id"] for item in archive.json()}


def test_memory_catalog_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/memory")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_rejects_invalid_budget() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/replications",
            json={
                "source_url": "https://arxiv.org/abs/1706.03762",
                "budget": {"max_attempts": 0, "max_job_minutes": 10, "max_usd": 1},
            },
        )
        assert response.status_code == 422


def test_empty_evidence_report_is_honest() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/replications", json={"source_url": "https://arxiv.org/abs/1706.03762"}
        ).json()
        report = client.get(f"/replications/{created['id']}/report")
        assert report.status_code == 200
        assert "EVIDENCE REPORT" in report.text
        assert "REPRODUCED" not in report.text
