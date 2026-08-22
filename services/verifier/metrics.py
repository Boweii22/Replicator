import json
import math
from dataclasses import dataclass, field


class EvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Measurement:
    value: float
    metric_name: str = ""
    unit: str = ""
    data_source: str = "legacy"
    dataset_names: list[str] = field(default_factory=list)
    dataset_count: int = 0
    sample_count: int = 0
    protocol: str = ""
    legacy: bool = False


def load_metrics_bytes(payload: bytes) -> dict[str, Measurement]:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvidenceError("Metrics artifact is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceError("Metrics artifact must contain an object")
    result: dict[str, Measurement] = {}
    for claim_id, value in parsed.items():
        if not isinstance(claim_id, str) or not claim_id:
            raise EvidenceError("Metrics artifact contains an invalid claim ID")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                raise EvidenceError(f"Metric for {claim_id} is not a finite number")
            result[claim_id] = Measurement(value=float(value), legacy=True)
            continue
        if not isinstance(value, dict):
            raise EvidenceError(f"Metric for {claim_id} is not a measurement object")
        required = {
            "value", "metric_name", "unit", "data_source", "dataset_names",
            "dataset_count", "sample_count", "protocol",
        }
        if not required.issubset(value):
            raise EvidenceError(f"Metric for {claim_id} is missing provenance fields")
        number = value["value"]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise EvidenceError(f"Metric for {claim_id} is not a finite number")
        if not isinstance(value["dataset_names"], list) or not all(
            isinstance(name, str) and name.strip() for name in value["dataset_names"]
        ):
            raise EvidenceError(f"Metric for {claim_id} has invalid dataset names")
        result[claim_id] = Measurement(
            value=float(number),
            metric_name=str(value["metric_name"]),
            unit=str(value["unit"]),
            data_source=str(value["data_source"]),
            dataset_names=value["dataset_names"],
            dataset_count=int(value["dataset_count"]),
            sample_count=int(value["sample_count"]),
            protocol=str(value["protocol"]),
        )
    return result
