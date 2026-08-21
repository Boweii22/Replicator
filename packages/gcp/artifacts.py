from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


class ArtifactStore:
    """Immutable artifact writer with a filesystem mode for local development."""

    def __init__(self, bucket: str | None = None, local_root: Path | None = None) -> None:
        self.bucket = bucket or os.getenv("ARTIFACT_BUCKET")
        self.local_root = local_root or Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".artifacts"))

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        safe_key = self._safe_key(key)
        if self.bucket:
            from google.api_core.exceptions import PreconditionFailed
            from google.cloud import storage

            blob = storage.Client().bucket(self.bucket).blob(safe_key)
            try:
                blob.upload_from_string(data, content_type=content_type, if_generation_match=0)
            except PreconditionFailed:
                if blob.download_as_bytes() != data:
                    raise FileExistsError(
                        f"Artifact already exists with different bytes: {safe_key}"
                    ) from None
            return f"gs://{self.bucket}/{safe_key}"
        target = self.local_root / Path(safe_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            if target.read_bytes() != data:
                raise
        return target.resolve().as_uri()

    def get_bytes(self, uri: str) -> bytes:
        if uri.startswith("gs://"):
            from google.cloud import storage

            bucket_name, key = uri.removeprefix("gs://").split("/", 1)
            return storage.Client().bucket(bucket_name).blob(key).download_as_bytes()
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError("Only gs:// and file:// evidence URIs are supported")
        path = (
            Path(unquote(parsed.path.lstrip("/")))
            if os.name == "nt"
            else Path(unquote(parsed.path))
        )
        return path.read_bytes()

    def list_uris(self, prefix_uri: str) -> list[str]:
        if prefix_uri.startswith("gs://"):
            from google.cloud import storage

            bucket_name, prefix = prefix_uri.removeprefix("gs://").split("/", 1)
            return [
                f"gs://{bucket_name}/{blob.name}"
                for blob in storage.Client().list_blobs(bucket_name, prefix=prefix)
            ]
        parsed = urlparse(prefix_uri)
        if parsed.scheme != "file":
            raise ValueError("Only gs:// and file:// artifact prefixes are supported")
        root = (
            Path(unquote(parsed.path.lstrip("/")))
            if os.name == "nt"
            else Path(unquote(parsed.path))
        )
        return [path.resolve().as_uri() for path in root.rglob("*") if path.is_file()]

    @staticmethod
    def _safe_key(key: str) -> str:
        path = PurePosixPath(key)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Artifact key must stay within the replication prefix")
        return str(path)


artifacts = ArtifactStore()
