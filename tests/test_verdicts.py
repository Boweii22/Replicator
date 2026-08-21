import pytest

from packages.schemas.models import VerdictStatus
from packages.science import numeric_verdict


@pytest.mark.parametrize(
    ("reported", "obtained", "expected"),
    [
        (100, 104, VerdictStatus.REPRODUCED),
        (100, 110, VerdictStatus.PARTIAL),
        (100, 116, VerdictStatus.FAILED),
        (-100, -104, VerdictStatus.REPRODUCED),
        (0, 0.04, VerdictStatus.REPRODUCED),
    ],
)
def test_numeric_verdict_rubric(reported: float, obtained: float, expected: VerdictStatus) -> None:
    status, delta = numeric_verdict(reported, obtained, 5)
    assert status == expected
    assert delta >= 0


def test_numeric_verdict_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        numeric_verdict(1, float("nan"), 5)
