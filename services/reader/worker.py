from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.gcp.artifacts import ArtifactStore
from packages.gcp.pubsub import LocalEventBus
from packages.gcp.state import InMemoryState
from packages.schemas.models import Claim, Event, ReplicationStatus, WorkMessage
from services.reader.extractor import ClaimsExtractor
from services.reader.pdf import extract_pdf, fetch_pdf


class ReaderWorker:
    def __init__(
        self,
        state: InMemoryState,
        bus: LocalEventBus,
        artifacts: ArtifactStore,
        extractor: ClaimsExtractor,
    ) -> None:
        self.state = state
        self.bus = bus
        self.artifacts = artifacts
        self.extractor = extractor

    async def handle(self, message: WorkMessage) -> None:
        if not await self.state.claim_event(message.event_id):
            return
        replication = await self.state.get_replication(message.replication_id)
        if replication is None:
            raise ValueError("Unknown replication")
        await self.state.transition(
            replication.id, {ReplicationStatus.QUEUED}, ReplicationStatus.READING
        )
        pdf = await fetch_pdf(replication.source_url)
        pdf_uri = self.artifacts.put_bytes(
            f"{replication.id}/paper/source.pdf", pdf, "application/pdf"
        )
        with tempfile.TemporaryDirectory(prefix="replicator-reader-") as temp:
            extraction = extract_pdf(pdf, Path(temp))
            result = await self.extractor.extract(extraction)
            figure_uris = []
            for index, figure_path in enumerate(extraction.figure_paths, start=1):
                path = Path(figure_path)
                figure_uris.append(self.artifacts.put_bytes(
                    f"{replication.id}/paper/figures/{index:03d}{path.suffix.lower()}",
                    path.read_bytes(),
                    "image/png" if path.suffix.lower() == ".png" else "application/octet-stream",
                ))
            extraction.figure_paths = figure_uris
        await self.state.set_paper_metadata(
            replication.id, title=extraction.title, authors=extraction.authors, pdf_uri=pdf_uri
        )
        manifest_uri = self.artifacts.put_bytes(
            f"{replication.id}/reader/extraction.json",
            json.dumps(extraction.model_dump(mode="json"), indent=2).encode(),
            "application/json",
        )
        if extraction.injection_suspected:
            await self.state.append_event(Event(
                replication_id=replication.id,
                kind="security",
                stage="reader",
                message="Prompt injection suspected; source remains quarantined as untrusted data",
                detail={"rules": extraction.injection_reasons},
            ))
        claims = []
        for index, candidate in enumerate(result.claims):
            data = candidate.model_dump()
            image_index = data.pop("figure_image_index")
            figure_uri = (extraction.figure_paths[image_index]
                if image_index is not None and image_index < len(extraction.figure_paths) else None)
            claims.append(Claim(replication_id=replication.id, index=index,
                figure_gcs_uri=figure_uri, **data))
        await self.state.put_claims(replication.id, claims)
        await self.state.set_paper_metadata(
            replication.id, title=result.title, authors=result.authors, pdf_uri=pdf_uri
        )
        await self.state.append_event(Event(
            replication_id=replication.id,
            kind="artifact",
            stage="reader",
            message=(
                f"Extracted {extraction.page_count} pages and {len(claims)} quantitative claims; "
                "evidence manifest persisted"
            ),
            detail={
                "pdf_uri": pdf_uri,
                "manifest_uri": manifest_uri,
                "feasible_claims": sum(claim.feasible for claim in claims),
            },
        ))
        await self.state.transition(
            replication.id, {ReplicationStatus.READING}, ReplicationStatus.PLANNING
        )
        await self.bus.publish("plan.ready", WorkMessage(
            event_type="plan.ready",
            replication_id=replication.id,
            trace_id=message.trace_id,
        ))
