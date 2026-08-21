from __future__ import annotations

import math

from packages.schemas.models import VerdictStatus


def numeric_verdict(
    reported: float, obtained: float, tolerance_pct: float
) -> tuple[VerdictStatus, float]:
    """Apply the public verdict rubric without model discretion."""
    if not all(math.isfinite(value) for value in (reported, obtained, tolerance_pct)):
        raise ValueError("Verdict inputs must be finite")
    if tolerance_pct <= 0:
        raise ValueError("Tolerance must be positive")
    denominator = abs(reported)
    delta_pct = abs(obtained - reported) * 100 if denominator == 0 else abs(obtained - reported) / denominator * 100
    if delta_pct <= tolerance_pct:
        return VerdictStatus.REPRODUCED, delta_pct
    if delta_pct <= tolerance_pct * 3:
        return VerdictStatus.PARTIAL, delta_pct
    return VerdictStatus.FAILED, delta_pct
