from contextlib import contextmanager
from typing import Any, Iterator

try:
    from opentelemetry import trace
except ModuleNotFoundError:  # Minimal local contract tests need no cloud telemetry install.
    trace = None


class _LocalSpan:
    """No-op span used only when the optional telemetry runtime is unavailable."""


tracer = trace.get_tracer("replicator") if trace else None


@contextmanager
def replication_span(name: str, **attributes: str) -> Iterator[Any]:
    if tracer is None:
        yield _LocalSpan()
        return
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span
