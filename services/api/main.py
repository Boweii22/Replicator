from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from packages.gcp.artifacts import ArtifactStore
from packages.gcp.pubsub import bus
from packages.gcp.state import state
from packages.schemas.models import (
    Claim,
    Event,
    Memory,
    Replication,
    ReplicationCreate,
    Verdict,
    WorkMessage,
)
from packages.telemetry import configure_telemetry, replication_span
from services.demo import run_calibration_mission
from services.pipeline import register_local_pipeline
from services.reporter.report import render_report

configure_telemetry()

app = FastAPI(title="Replicator API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
if os.getenv("K_SERVICE"):
    from packages.gcp.cloud_pubsub import CloudEventBus
    from packages.gcp.firestore_state import FirestoreState

    app_state = FirestoreState()
    event_bus = CloudEventBus()
else:
    app_state = state
    event_bus = bus
    register_local_pipeline()


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/replications", response_model=Replication, status_code=202)
async def create_replication(payload: ReplicationCreate) -> Replication:
    replication = Replication(source_url=str(payload.source_url), budget=payload.budget)
    with replication_span(
        "api.replication.create",
        replication_id=replication.id,
        trace_id=replication.trace_id,
        model="none",
    ):
        await app_state.create_replication(replication)
        await app_state.append_event(
            Event(
                replication_id=replication.id,
                kind="status",
                stage="api",
                message="Replication queued with enforced budget caps",
                detail={"budget": payload.budget.model_dump()},
            )
        )
        await event_bus.publish(
            "replication.requested",
            WorkMessage(
                event_type="replication.requested",
                replication_id=replication.id,
                trace_id=replication.trace_id,
            ),
        )
    return replication


@app.post("/demo/calibration", response_model=Replication, status_code=201)
async def calibration_demo() -> Replication:
    if os.getenv("K_SERVICE"):
        raise HTTPException(status_code=403, detail="Calibration fixture is local-only")
    return await run_calibration_mission()


@app.get("/replications/{replication_id}", response_model=Replication)
async def get_replication(replication_id: str) -> Replication:
    replication = await app_state.get_replication(replication_id)
    if not replication:
        raise HTTPException(status_code=404, detail="Replication not found")
    return replication


@app.get("/replications", response_model=list[Replication])
async def list_replications() -> list[Replication]:
    return await app_state.list_replications()


@app.get("/memory", response_model=list[Memory])
async def list_memory() -> list[Memory]:
    return await app_state.list_memories()


@app.get("/replications/{replication_id}/claims", response_model=list[Claim])
async def get_claims(replication_id: str) -> list[Claim]:
    if not await app_state.get_replication(replication_id):
        raise HTTPException(status_code=404, detail="Replication not found")
    return await app_state.list_claims(replication_id)


@app.get("/replications/{replication_id}/verdicts", response_model=list[Verdict])
async def get_verdicts(replication_id: str) -> list[Verdict]:
    if not await app_state.get_replication(replication_id):
        raise HTTPException(status_code=404, detail="Replication not found")
    return await app_state.list_verdicts(replication_id)


@app.get("/replications/{replication_id}/report", response_class=HTMLResponse)
async def get_report(replication_id: str) -> HTMLResponse:
    replication = await app_state.get_replication(replication_id)
    if not replication:
        raise HTTPException(status_code=404, detail="Replication not found")
    return HTMLResponse(
        render_report(
            replication,
            await app_state.list_claims(replication_id),
            await app_state.list_verdicts(replication_id),
        )
    )


@app.get("/replications/{replication_id}/artifact")
async def get_artifact(replication_id: str, uri: str = Query()) -> Response:
    if not await app_state.get_replication(replication_id):
        raise HTTPException(status_code=404, detail="Replication not found")
    store = ArtifactStore()
    if uri.startswith("gs://"):
        expected = f"gs://{store.bucket}/{replication_id}/"
        if not store.bucket or not uri.startswith(expected):
            raise HTTPException(status_code=403, detail="Artifact is outside this replication")
    else:
        from urllib.parse import unquote, urlparse

        parsed = urlparse(uri)
        candidate, expected_root = await asyncio.to_thread(
            lambda: (
                Path(unquote(parsed.path.lstrip("/"))).resolve(),
                (store.local_root / replication_id).resolve(),
            )
        )
        if parsed.scheme != "file" or not candidate.is_relative_to(expected_root):
            raise HTTPException(status_code=403, detail="Artifact is outside this replication")
    try:
        payload = store.get_bytes(uri)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Artifact not found") from None
    media_type = (
        "image/png" if uri.lower().split("?", 1)[0].endswith(".png") else "application/octet-stream"
    )
    return Response(
        payload, media_type=media_type, headers={"Cache-Control": "private, max-age=300"}
    )


@app.get("/replications/{replication_id}/events")
async def events(replication_id: str, after: int = Query(default=0, ge=0)) -> StreamingResponse:
    if not await app_state.get_replication(replication_id):
        raise HTTPException(status_code=404, detail="Replication not found")

    async def generate():
        async for event in app_state.stream_events(replication_id, after):
            payload = json.dumps(event.model_dump(mode="json"))
            yield f"id: {event.sequence}\nevent: {event.kind}\ndata: {payload}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


WEB_DIR = Path(__file__).resolve().parents[2] / "apps" / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
