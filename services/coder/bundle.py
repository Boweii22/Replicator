from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from pathlib import PurePosixPath

REQUIRED_FILES = {"Dockerfile", "run.py", "requirements.txt", "replicator_contract.py"}


def build_source_bundle(files: dict[str, str]) -> tuple[bytes, str]:
    """Return a byte-for-byte deterministic tar.gz and its SHA-256 digest."""
    missing = REQUIRED_FILES - files.keys()
    if missing:
        raise ValueError(f"Generated experiment is missing: {', '.join(sorted(missing))}")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name in sorted(files):
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"Unsafe generated path: {name}")
                content = files[name].encode("utf-8")
                info = tarfile.TarInfo(str(path))
                info.size = len(content)
                info.mtime = 0
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                archive.addfile(info, io.BytesIO(content))
    payload = buffer.getvalue()
    return payload, hashlib.sha256(payload).hexdigest()


def default_contract_source() -> str:
    from inspect import getsource

    from runner.replicator_contract import ContractViolation, validate_outputs

    return (
        "from __future__ import annotations\n"
        "import json\nimport math\nfrom pathlib import Path\n\n"
        + getsource(ContractViolation)
        + "\n"
        + getsource(validate_outputs)
    )
