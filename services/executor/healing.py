from __future__ import annotations

import hashlib
import re

SIGNATURE = re.compile(r"ERROR_SIGNATURE:([^\r\n]+)")


def extract_error_signature(stderr: str) -> str:
    match = SIGNATURE.search(stderr)
    if match:
        return match.group(1).strip()[:240]
    lowered = stderr.lower()
    if (
        "invalid dataset name" in lowered
        or "all download strategies failed" in lowered
        or "file is not a zip file" in lowered
        or ("httperror" in lowered and "404" in lowered)
    ):
        return "dataset-source-unavailable"
    if "cannot import name 'minirocketclassifier'" in lowered:
        return "unsupported-sktime-minirocketclassifier-api"
    normalized = re.sub(r"0x[0-9a-f]+|\d+", "#", stderr.lower())[-2000:]
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"unclassified-{digest}"


def memory_key(library: str, signature: str) -> str:
    digest = hashlib.sha256(signature.encode()).hexdigest()[:20]
    safe_library = re.sub(r"[^a-z0-9_.-]", "-", library.lower())[:60]
    return f"{safe_library}::{digest}"
