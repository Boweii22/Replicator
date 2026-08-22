from __future__ import annotations

from packages.schemas.models import Event, Verdict, VerdictStatus, WorkMessage
from services.verifier.figures import figure_similarity
from services.verifier.metrics import load_metrics_bytes
from services.verifier.verifier import (
    evidence_contract_error,
    verify_figure_claim,
    verify_numeric_claim,
)
from services.verifier.vision import GeminiVisionAssessor


class VerifierWorker:
    def __init__(self, state, bus, artifacts, vision=None) -> None:
        self.state, self.bus, self.artifacts = state, bus, artifacts
        self.vision = vision

    async def handle(self, message: WorkMessage) -> None:
        if not await self.state.claim_event(message.event_id):
            return
        attempt = await self.state.get_attempt(message.attempt_id) if message.attempt_id else None
        replication = await self.state.get_replication(message.replication_id)
        if replication is None:
            raise ValueError("Unknown replication")
        if attempt is None or not attempt.metrics_gcs_uri:
            raise ValueError("Verifier requires an attempt with a metrics artifact")
        metrics = load_metrics_bytes(self.artifacts.get_bytes(attempt.metrics_gcs_uri))
        claims = await self.state.list_claims(message.replication_id)
        contract_error = evidence_contract_error(claims, metrics)
        if contract_error:
            links = [uri for uri in (attempt.metrics_gcs_uri, attempt.stdout_gcs_uri) if uri]
            verdicts = [
                Verdict(
                    claim_id=claim.id,
                    attempt_id=attempt.id,
                    status=VerdictStatus.NOT_ATTEMPTED,
                    reasoning=(
                        "Evidence contract failed; no scientific verdict was assigned. "
                        + contract_error
                    ),
                    evidence_links=links,
                )
                for claim in claims
            ]
            for verdict in verdicts:
                await self.state.put_verdict(verdict)
            await self.state.append_event(
                Event(
                    replication_id=message.replication_id,
                    kind="agent.decision",
                    stage="verifier",
                    message="Rejected a semantically inconsistent metrics artifact",
                    detail={"attempt_id": attempt.id, "reason": contract_error},
                )
            )
            await self.bus.publish(
                "report.ready",
                WorkMessage(
                    event_type="report.ready",
                    replication_id=message.replication_id,
                    plan_id=message.plan_id,
                    attempt_id=attempt.id,
                    trace_id=message.trace_id,
                ),
            )
            return
        verdicts = []
        for claim in claims:
            if not claim.feasible:
                verdicts.append(
                    Verdict(
                        claim_id=claim.id,
                        attempt_id=attempt.id,
                        status=VerdictStatus.NOT_ATTEMPTED,
                        reasoning=claim.feasibility_reason or "Claim was declared infeasible.",
                        evidence_links=[uri for uri in [replication.pdf_gcs_uri] if uri],
                    )
                )
                continue
            if claim.claim_type == "figure" and claim.figure_gcs_uri:
                reproduced_uri = next(
                    (uri for uri in attempt.figures_gcs_uri if uri.endswith(f"/{claim.id}.png")),
                    None,
                )
                if reproduced_uri is None:
                    verdicts.append(
                        Verdict(
                            claim_id=claim.id,
                            attempt_id=attempt.id,
                            status=VerdictStatus.FAILED,
                            reasoning=(
                                "The successful job did not produce the required claim figure."
                            ),
                            evidence_links=[attempt.metrics_gcs_uri],
                        )
                    )
                    continue
                paper = self.artifacts.get_bytes(claim.figure_gcs_uri)
                reproduced = self.artifacts.get_bytes(reproduced_uri)
                if self.vision is None:
                    self.vision = GeminiVisionAssessor()
                assessment = await self.vision.compare(paper, reproduced)
                verdicts.append(
                    verify_figure_claim(
                        claim,
                        attempt,
                        reproduced_uri,
                        figure_similarity(paper, reproduced),
                        assessment,
                    )
                )
            else:
                verdicts.append(verify_numeric_claim(claim, attempt, metrics))
        for verdict in verdicts:
            await self.state.put_verdict(verdict)
        await self.state.append_event(
            Event(
                replication_id=message.replication_id,
                kind="agent.decision",
                stage="verifier",
                message=f"Resolved {len(verdicts)} claims from immutable metrics evidence",
                detail={
                    "attempt_id": attempt.id,
                    "verdicts": {
                        status: sum(v.status == status for v in verdicts)
                        for status in ("REPRODUCED", "PARTIAL", "FAILED", "NOT_ATTEMPTED")
                    },
                },
            )
        )
        await self.bus.publish(
            "report.ready",
            WorkMessage(
                event_type="report.ready",
                replication_id=message.replication_id,
                plan_id=message.plan_id,
                attempt_id=attempt.id,
                trace_id=message.trace_id,
            ),
        )
