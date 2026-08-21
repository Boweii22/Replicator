from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


class ArtifactStore:
    """Immutable artifact writer with a filesystem mode for local development."""

    def __init__(self, bucket: str | None = None, local_root: Path | None = None) -> None:
        self.bucket = bucket or os.getenv("ARTIFACT_BUCKET")
        self.local_root = local_root or Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".artifacts"))

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        safe_key = self._safe_key(key)
        if self.bucket:
            from google.cloud import storage

            blob = storage.Client().bucket(self.bucket).blob(safe_key)
            blob.upload_from_string(data, content_type=content_type, if_generation_match=0)
            return f"gs://{self.bucket}/{safe_key}"
        target = self.local_root / Path(safe_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
        return target.resolve().as_uri()

    @staticmethod
    def _safe_key(key: str) -> str:
        path = PurePosixPath(key)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Artifact key must stay within the replication prefix")
        return str(path)


artifacts = ArtifactStore()
