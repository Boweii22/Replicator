from __future__ import annotations

import asyncio
import json

from packages.schemas.models import Event, WorkMessage
from services.reporter.report import create_manifest, render_badge, render_report


class ReporterWorker:
    def __init__(self, state, artifacts, signer=None) -> None:
        self.state, self.artifacts, self.signer = state, artifacts, signer

    async def handle(self, message: WorkMessage) -> None:
        if not await self.state.claim_event(message.event_id):
            return
        replication = await self.state.get_replication(message.replication_id)
        if replication is None:
            raise ValueError("Unknown replication")
        claims = await self.state.list_claims(replication.id)
        verdicts = await self.state.list_verdicts(replication.id)
        report = render_report(replication, claims, verdicts).encode()
        manifest = create_manifest(replication.id, report, verdicts)
        if self.signer:
            canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode()
            manifest.signature = await asyncio.to_thread(self.signer.sign, canonical)
            manifest.signature_algorithm = "GOOGLE_IAM_SIGNBLOB"
        prefix = f"{replication.id}/report"
        report_uri = self.artifacts.put_bytes(f"{prefix}/report.html", report, "text/html")
        manifest_uri = self.artifacts.put_bytes(
            f"{prefix}/manifest.json",
            manifest.model_dump_json(indent=2).encode(),
            "application/json",
        )
        reproduced = sum(verdict.status == "REPRODUCED" for verdict in verdicts)
        self.artifacts.put_bytes(
            f"{prefix}/badge.svg", render_badge(reproduced, len(claims)).encode(), "image/svg+xml"
        )
        await self.state.finish_report(
            replication.id,
            report_uri=report_uri,
            summary=f"{reproduced}/{len(claims)} claims reproduced",
        )
        await self.state.append_event(
            Event(
                replication_id=replication.id,
                kind="artifact",
                stage="reporter",
                message="Signed replication report is ready",
                detail={
                    "report_uri": report_uri,
                    "manifest_uri": manifest_uri,
                    "signature_algorithm": manifest.signature_algorithm,
                },
            )
        )
