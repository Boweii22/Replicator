from __future__ import annotations

import time
from typing import Any, Protocol

from packages.gcp.cloudbuild import BuildRequest, build_spec
from packages.gcp.cloudrun_jobs import JobRequest, job_spec


class Response(Protocol):
    def raise_for_status(self) -> None: ...
    def json(self) -> dict[str, Any]: ...


class Session(Protocol):
    def post(self, url: str, *, json: dict | None = None, timeout: int = 60) -> Response: ...
    def get(self, url: str, *, timeout: int = 60) -> Response: ...


class GoogleExecutionApi:
    """Small REST boundary around Cloud Build and Cloud Run v2, injectable in tests."""

    def __init__(self, session: Session | None = None) -> None:
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            session = AuthorizedSession(credentials)
        self.session = session

    def submit_build(self, request: BuildRequest) -> str:
        url = (
            f"https://cloudbuild.googleapis.com/v1/projects/{request.project}"
            f"/locations/{request.region}/builds"
        )
        response = self.session.post(url, json=build_spec(request), timeout=60)
        response.raise_for_status()
        operation = response.json()
        build_id = operation.get("metadata", {}).get("build", {}).get("id")
        if not build_id:
            raise RuntimeError("Cloud Build returned no build ID")
        return f"projects/{request.project}/locations/{request.region}/builds/{build_id}"

    def create_job(self, request: JobRequest) -> str:
        url = (
            f"https://run.googleapis.com/v2/projects/{request.project}/locations/{request.region}"
            f"/jobs?jobId={request.job_name}"
        )
        response = self.session.post(url, json=job_spec(request), timeout=60)
        response.raise_for_status()
        operation = response.json()
        return self._require_operation(operation, "Cloud Run job creation")

    def run_job(self, request: JobRequest) -> str:
        job = f"projects/{request.project}/locations/{request.region}/jobs/{request.job_name}"
        response = self.session.post(
            f"https://run.googleapis.com/v2/{job}:run", json={}, timeout=60
        )
        response.raise_for_status()
        return self._require_operation(response.json(), "Cloud Run job execution")

    def wait_operation(self, operation_name: str, *, timeout_seconds: int = 1200) -> dict:
        deadline = time.monotonic() + timeout_seconds
        url = f"https://run.googleapis.com/v2/{operation_name}"
        while time.monotonic() < deadline:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            operation = response.json()
            if operation.get("done"):
                if "error" in operation:
                    raise RuntimeError(f"Google operation failed: {operation['error']}")
                return operation.get("response", {})
            time.sleep(2)
        raise TimeoutError(f"Google operation exceeded {timeout_seconds}s")

    def wait_build(self, build_name: str, *, timeout_seconds: int = 1200) -> dict:
        deadline = time.monotonic() + timeout_seconds
        url = f"https://cloudbuild.googleapis.com/v1/{build_name}"
        while time.monotonic() < deadline:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            build = response.json()
            status = build.get("status")
            if status == "SUCCESS":
                return build
            if status in {"FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}:
                detail = (
                    build.get("statusDetail")
                    or build.get("failureInfo", {}).get("detail")
                    or build.get("logUrl")
                    or "no detail"
                )
                raise RuntimeError(f"Cloud Build {status}: {detail}")
            time.sleep(2)
        raise TimeoutError(f"Cloud Build exceeded {timeout_seconds}s")

    def _poll(self, url: str, timeout_seconds: int) -> dict:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            operation = response.json()
            if operation.get("done"):
                if "error" in operation:
                    raise RuntimeError(f"Google operation failed: {operation['error']}")
                return operation.get("response", {})
            time.sleep(2)
        raise TimeoutError(f"Google operation exceeded {timeout_seconds}s")

    @staticmethod
    def _require_operation(payload: dict, action: str) -> str:
        name = payload.get("name")
        if not name:
            raise RuntimeError(f"{action} returned no operation name")
        return name
