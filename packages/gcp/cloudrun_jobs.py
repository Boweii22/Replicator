from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobRequest:
    project: str
    region: str
    job_name: str
    image_uri: str
    service_account: str
    replication_id: str
    attempt_id: str
    output_uri: str
    timeout_seconds: int
    cpu: str = "4"
    memory: str = "8Gi"


def job_spec(request: JobRequest) -> dict:
    if not 1 <= request.timeout_seconds <= 3600:
        raise ValueError("Experiment timeout must be between 1 second and 1 GPU-safe hour")
    return {
        "template": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "serviceAccount": request.service_account,
                "timeout": f"{request.timeout_seconds}s",
                "maxRetries": 0,
                "containers": [
                    {
                        "image": request.image_uri,
                        "args": ["--out", "/out"],
                        "env": [
                            {"name": "REPLICATION_ID", "value": request.replication_id},
                            {"name": "ATTEMPT_ID", "value": request.attempt_id},
                            {"name": "OUTPUT_GCS_URI", "value": request.output_uri},
                        ],
                        "resources": {
                            "limits": {"cpu": request.cpu, "memory": request.memory},
                            "cpuIdle": False,
                        },
                    }
                ],
            },
        },
        "labels": {"replication-id": request.replication_id[:63]},
    }
