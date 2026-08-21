import json
import logging

from packages.telemetry.setup import JsonFormatter


def test_structured_logs_carry_correlation_ids() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "step complete", (), None)
    record.replication_id = "rep-1"
    record.attempt_id = "attempt-2"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["replication_id"] == "rep-1"
    assert payload["attempt_id"] == "attempt-2"
