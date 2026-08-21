import base64

from fastapi.testclient import TestClient

from services.worker_main import app


def test_worker_rejects_invalid_pubsub_payload() -> None:
    with TestClient(app) as client:
        response = client.post("/pubsub", json={"message": {"data": "not-base64!"}})
        assert response.status_code == 400


def test_worker_rejects_wrong_work_message_without_cloud_calls() -> None:
    encoded = base64.b64encode(b'{"event_type":"x"}').decode()
    with TestClient(app) as client:
        response = client.post("/pubsub", json={"message": {"data": encoded}})
        assert response.status_code == 400
