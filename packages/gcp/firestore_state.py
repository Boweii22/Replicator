from __future__ import annotations

import os
import asyncio

from packages.gcp.state import ConflictError
from packages.schemas.models import (
    Attempt,
    Claim,
    Event,
    ExperimentPlan,
    Memory,
    Replication,
    ReplicationStatus,
    Spend,
    Verdict,
    utcnow,
)


class FirestoreState:
    """Production state operations used by stateless push workers."""

    def __init__(self, project: str | None = None, database: str | None = None) -> None:
        from google.cloud import firestore

        self.firestore = firestore
        self.client = firestore.AsyncClient(
            project=project or os.getenv("GOOGLE_CLOUD_PROJECT"),
            database=database or os.getenv("FIRESTORE_DATABASE", "replicator"),
        )

    async def create_replication(self, replication: Replication) -> Replication:
        ref = self.client.collection("replications").document(replication.id)
        await ref.create(replication.model_dump(mode="python"))
        return replication

    async def get_replication(self, replication_id: str) -> Replication | None:
        snapshot = await self.client.collection("replications").document(replication_id).get()
        return Replication.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def claim_event(self, event_id: str) -> bool:
        ref = self.client.collection("processed_events").document(event_id)
        transaction = self.client.transaction()

        @self.firestore.async_transactional
        async def claim(txn):
            snapshot = await ref.get(transaction=txn)
            if snapshot.exists:
                return False
            txn.create(ref, {"processed_at": utcnow()})
            return True

        return await claim(transaction)

    async def release_event(self, event_id: str) -> None:
        await self.client.collection("processed_events").document(event_id).delete()

    async def transition(
        self, replication_id: str, expected: set[ReplicationStatus], target: ReplicationStatus
    ) -> Replication:
        ref = self.client.collection("replications").document(replication_id)
        transaction = self.client.transaction()

        @self.firestore.async_transactional
        async def apply(txn):
            snapshot = await ref.get(transaction=txn)
            if not snapshot.exists:
                raise KeyError(replication_id)
            current = Replication.model_validate(snapshot.to_dict())
            if current.status not in expected:
                raise ConflictError(f"expected {expected}, found {current.status}")
            current.status = target
            current.updated_at = utcnow()
            txn.set(ref, current.model_dump(mode="python"))
            return current

        return await apply(transaction)

    async def set_paper_metadata(
        self, replication_id: str, *, title: str, authors: list[str], pdf_uri: str
    ) -> Replication:
        ref = self.client.collection("replications").document(replication_id)
        await ref.update({"title": title, "authors": authors, "pdf_gcs_uri": pdf_uri,
            "updated_at": utcnow()})
        result = await self.get_replication(replication_id)
        if result is None:
            raise KeyError(replication_id)
        return result

    async def put_claims(self, replication_id: str, claims: list[Claim]) -> None:
        batch = self.client.batch()
        for claim in claims:
            ref = self.client.collection("claims").document(claim.id)
            batch.set(ref, claim.model_dump(mode="python"))
        await batch.commit()

    async def list_claims(self, replication_id: str) -> list[Claim]:
        query = self.client.collection("claims").where("replication_id", "==", replication_id)
        claims = [Claim.model_validate(doc.to_dict()) async for doc in query.stream()]
        return sorted(claims, key=lambda claim: claim.index)

    async def put_verdict(self, verdict: Verdict) -> None:
        await self.client.collection("verdicts").document(verdict.id).set(
            verdict.model_dump(mode="python")
        )

    async def list_verdicts(self, replication_id: str) -> list[Verdict]:
        claim_ids = {claim.id for claim in await self.list_claims(replication_id)}
        if not claim_ids:
            return []
        verdicts = []
        async for doc in self.client.collection("verdicts").stream():
            verdict = Verdict.model_validate(doc.to_dict())
            if verdict.claim_id in claim_ids:
                verdicts.append(verdict)
        return verdicts

    async def put_plan(self, plan: ExperimentPlan) -> None:
        await self.client.collection("plans").document(plan.id).set(plan.model_dump(mode="python"))

    async def get_plan(self, plan_id: str) -> ExperimentPlan | None:
        snapshot = await self.client.collection("plans").document(plan_id).get()
        return ExperimentPlan.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def put_attempt(self, attempt: Attempt) -> None:
        await self.client.collection("attempts").document(attempt.id).set(
            attempt.model_dump(mode="python")
        )

    async def get_attempt(self, attempt_id: str) -> Attempt | None:
        snapshot = await self.client.collection("attempts").document(attempt_id).get()
        return Attempt.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def list_attempts(self, plan_id: str) -> list[Attempt]:
        query = self.client.collection("attempts").where("plan_id", "==", plan_id)
        attempts = [Attempt.model_validate(doc.to_dict()) async for doc in query.stream()]
        return sorted(attempts, key=lambda attempt: attempt.n)

    async def add_spend(self, replication_id: str, *, usd: float, job_minutes: float) -> Spend:
        ref = self.client.collection("replications").document(replication_id)
        transaction = self.client.transaction()

        @self.firestore.async_transactional
        async def apply(txn):
            snapshot = await ref.get(transaction=txn)
            replication = Replication.model_validate(snapshot.to_dict())
            replication.spent.usd += usd
            replication.spent.job_minutes += job_minutes
            replication.updated_at = utcnow()
            txn.set(ref, replication.model_dump(mode="python"))
            return replication.spent

        return await apply(transaction)

    async def put_memory(self, memory: Memory) -> None:
        await self.client.collection("memory").document(memory.key).set(
            memory.model_dump(mode="python"), merge=True
        )

    async def get_memory(self, key: str) -> Memory | None:
        snapshot = await self.client.collection("memory").document(key).get()
        return Memory.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def finish_report(self, replication_id: str, *, report_uri: str, summary: str) -> Replication:
        ref = self.client.collection("replications").document(replication_id)
        await ref.update({"status": ReplicationStatus.REPORTED.value, "report_gcs_uri": report_uri,
            "summary_verdict": summary, "updated_at": utcnow()})
        result = await self.get_replication(replication_id)
        if result is None:
            raise KeyError(replication_id)
        return result

    async def append_event(self, event: Event) -> Event:
        ref = self.client.collection("replications").document(event.replication_id)
        event_ref = ref.collection("events").document()
        event.sequence = int(utcnow().timestamp() * 1_000_000)
        await event_ref.set(event.model_dump(mode="python"))
        return event

    async def stream_events(self, replication_id: str, after: int = 0):
        cursor = after
        while True:
            query = (self.client.collection("replications").document(replication_id)
                .collection("events").where("sequence", ">", cursor).order_by("sequence"))
            found = False
            async for doc in query.stream():
                event = Event.model_validate(doc.to_dict())
                cursor = max(cursor, event.sequence)
                found = True
                yield event
            if not found:
                await asyncio.sleep(2)
