from packages.gcp.cloudbuild import BuildRequest, build_spec
from packages.gcp.cloudrun_jobs import JobRequest, job_spec
from packages.gcp.execution_api import GoogleExecutionApi
from services.coder.bundle import build_source_bundle

FILES = {
    "Dockerfile": "FROM python:3.11-slim\nCOPY . /app",
    "run.py": "print('run')",
    "requirements.txt": "",
    "replicator_contract.py": "def validate(): pass",
}


def test_experiment_bundle_is_deterministic() -> None:
    first, first_hash = build_source_bundle(FILES)
    second, second_hash = build_source_bundle(dict(reversed(list(FILES.items()))))
    assert first == second
    assert first_hash == second_hash


def test_cloud_build_uses_provenance_and_dedicated_identity() -> None:
    spec = build_spec(
        BuildRequest(
            project="project",
            region="europe-west1",
            source_bucket="artifacts",
            source_object="run/source.tar.gz",
            image_uri="registry/image:attempt-1",
            service_account="builder@project.iam.gserviceaccount.com",
        )
    )
    assert spec["serviceAccount"].endswith("builder@project.iam.gserviceaccount.com")
    assert spec["options"]["sourceProvenanceHash"] == ["SHA256"]


def test_cloud_run_job_has_hard_limits_and_no_platform_retry() -> None:
    spec = job_spec(
        JobRequest(
            project="project",
            region="europe-west1",
            job_name="attempt-1",
            image_uri="registry/image@sha256:abc",
            service_account="runner@project.iam.gserviceaccount.com",
            replication_id="replication",
            attempt_id="attempt",
            output_uri="gs://bucket/run/attempt",
            timeout_seconds=1200,
        )
    )
    task = spec["template"]["template"]
    assert task["maxRetries"] == 0
    assert task["timeout"] == "1200s"
    assert task["containers"][0]["resources"]["limits"] == {"cpu": "4", "memory": "8Gi"}


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class RecordingSession:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def post(self, url: str, *, json: dict | None = None, timeout: int = 60) -> FakeResponse:
        self.posts.append((url, json or {}))
        return FakeResponse({"name": "operations/verified"})

    def get(self, url: str, *, timeout: int = 60) -> FakeResponse:
        return FakeResponse({"done": True, "response": {"name": "execution-1"}})


def test_execution_api_uses_regional_build_endpoint() -> None:
    session = RecordingSession()
    api = GoogleExecutionApi(session)
    operation = api.submit_build(
        BuildRequest(
            project="project",
            region="europe-west1",
            source_bucket="artifacts",
            source_object="run/source.tar.gz",
            image_uri="registry/image:attempt",
            service_account="builder@project.iam.gserviceaccount.com",
        )
    )
    assert operation == "operations/verified"
    assert "/locations/europe-west1/builds" in session.posts[0][0]
