import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

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
    trace_key = attributes.get("trace_id")
    parent = None
    if trace_key and len(trace_key) == 32:
        try:
            span_context = trace.SpanContext(
                trace_id=int(trace_key, 16),
                span_id=secrets.randbits(64) or 1,
                is_remote=True,
                trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
            )
            parent = trace.set_span_in_context(trace.NonRecordingSpan(span_context))
        except ValueError:
            parent = None
    with tracer.start_as_current_span(name, context=parent, attributes=attributes) as span:
        yield span
