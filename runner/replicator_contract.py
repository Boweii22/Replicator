from __future__ import annotations

import json
import math
from pathlib import Path


class ContractViolation(RuntimeError):
    pass


def validate_outputs(output_dir: Path, expected_claim_ids: set[str]) -> dict[str, float]:
    metrics_path = output_dir / "metrics.json"
    if not metrics_path.is_file():
        raise ContractViolation("ERROR_SIGNATURE:missing_metrics_json")
    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractViolation("ERROR_SIGNATURE:invalid_metrics_json") from exc
    if not isinstance(payload, dict):
        raise ContractViolation("ERROR_SIGNATURE:metrics_not_object")
    missing = expected_claim_ids - payload.keys()
    extra = payload.keys() - expected_claim_ids
    if missing:
        raise ContractViolation(f"ERROR_SIGNATURE:missing_claims:{','.join(sorted(missing))}")
    if extra:
        raise ContractViolation(f"ERROR_SIGNATURE:unknown_claims:{','.join(sorted(extra))}")
    metrics: dict[str, float] = {}
    for claim_id, value in payload.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ContractViolation(f"ERROR_SIGNATURE:nonfinite_metric:{claim_id}")
        metrics[claim_id] = float(value)
    return metrics
