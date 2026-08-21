from __future__ import annotations

import asyncio
import os
from datetime import timedelta

from packages.schemas.models import Replication, ReplicationStatus, utcnow

TERMINAL = {ReplicationStatus.REPORTED, ReplicationStatus.FAILED_SYSTEM}


def is_stalled(replication: Replication, cutoff) -> bool:
    return replication.status not in TERMINAL and replication.updated_at < cutoff


async def mark_stalled(timeout_minutes: int = 180) -> int:
    from google.cloud import firestore

    client = firestore.AsyncClient(
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        database=os.getenv("FIRESTORE_DATABASE", "replicator"),
    )
    cutoff = utcnow() - timedelta(minutes=timeout_minutes)
    count = 0
    async for document in client.collection("replications").stream():
        replication = Replication.model_validate(document.to_dict())
        if is_stalled(replication, cutoff):
            await document.reference.update(
                {
                    "status": ReplicationStatus.FAILED_SYSTEM.value,
                    "summary_verdict": "System timeout: no progress before janitor deadline",
                    "updated_at": utcnow(),
                }
            )
            count += 1
    return count


if __name__ == "__main__":
    print(f"marked_stalled={asyncio.run(mark_stalled())}")
