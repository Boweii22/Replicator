from __future__ import annotations

import base64
import os

from fastapi import FastAPI, Header, HTTPException, Response

from packages.gcp.artifacts import ArtifactStore
from packages.gcp.cloud_pubsub import CloudEventBus
from packages.gcp.firestore_state import FirestoreState
from packages.schemas.models import PubSubEnvelope, WorkMessage
from services.reader.extractor import VertexClaimsExtractor
from services.reader.worker import ReaderWorker

app = FastAPI(title="Replicator worker")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": os.getenv("SERVICE_NAME", "unknown")}


@app.post("/pubsub", status_code=204)
async def pubsub_push(
    envelope: PubSubEnvelope,
    authorization: str | None = Header(default=None),
) -> Response:
    if os.getenv("K_SERVICE") and not authorization:
        raise HTTPException(status_code=401, detail="Authenticated Pub/Sub push required")
    try:
        payload = base64.b64decode(envelope.message["data"], validate=True)
        message = WorkMessage.model_validate_json(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub envelope") from exc
    service = os.getenv("SERVICE_NAME", "reader")
    if service != "reader":
        raise HTTPException(status_code=501, detail=f"Worker {service} handler is not registered")
    worker = ReaderWorker(
        FirestoreState(), CloudEventBus(), ArtifactStore(), VertexClaimsExtractor()
    )
    await worker.handle(message)
    return Response(status_code=204)
