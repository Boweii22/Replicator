from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildRequest:
    project: str
    region: str
    source_bucket: str
    source_object: str
    image_uri: str
    service_account: str


def build_spec(request: BuildRequest) -> dict:
    return {
        "source": {
            "storageSource": {"bucket": request.source_bucket, "object": request.source_object}
        },
        "steps": [{
            "name": "gcr.io/cloud-builders/docker",
            "args": ["build", "--pull", "-t", request.image_uri, "."],
        }],
        "images": [request.image_uri],
        "serviceAccount": (
            f"projects/{request.project}/serviceAccounts/{request.service_account}"
        ),
        "options": {
            "logging": "CLOUD_LOGGING_ONLY",
            "sourceProvenanceHash": ["SHA256"],
            "requestedVerifyOption": "VERIFIED",
        },
        "timeout": "1200s",
    }
