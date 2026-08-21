import json
import math


class EvidenceError(RuntimeError):
    pass


def load_metrics_bytes(payload: bytes) -> dict[str, float]:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvidenceError("Metrics artifact is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceError("Metrics artifact must contain an object")
    result = {}
    for claim_id, value in parsed.items():
        if not isinstance(claim_id, str) or not claim_id:
            raise EvidenceError("Metrics artifact contains an invalid claim ID")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EvidenceError(f"Metric for {claim_id} is not a finite number")
        result[claim_id] = float(value)
    return result
