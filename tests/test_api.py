from fastapi.testclient import TestClient

from services.api.main import app


def test_mission_control_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Evidence, not vibes" in response.text


def test_create_get_and_budget_contract() -> None:
    with TestClient(app) as client:
        response = client.post("/replications", json={
            "source_url": "https://arxiv.org/abs/1706.03762",
            "budget": {"max_attempts": 2, "max_job_minutes": 10, "max_usd": 0.75},
        })
        assert response.status_code == 202
        created = response.json()
        assert created["status"] == "queued"
        assert created["budget"]["max_attempts"] == 2
        fetched = client.get(f"/replications/{created['id']}")
        assert fetched.status_code == 200


def test_rejects_invalid_budget() -> None:
    with TestClient(app) as client:
        response = client.post("/replications", json={
            "source_url": "https://arxiv.org/abs/1706.03762",
            "budget": {"max_attempts": 0, "max_job_minutes": 10, "max_usd": 1},
        })
        assert response.status_code == 422
